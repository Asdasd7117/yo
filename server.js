const express = require('express');
const fetch = require('node-fetch');
const { nanoid } = require('nanoid');
const getSlug = require('speakingurl');
const UAParser = require('ua-parser-js');
const db = require('./database');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static('public'));

// تهيئة قاعدة البيانات
db.initDB().then(() => {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`✅ السيرفر شغّال على المنفذ ${PORT}`);
  });
}).catch(err => {
  console.error('❌ خطأ في قاعدة البيانات:', err);
  process.exit(1);
});

// 🏠 الصفحة الرئيسية
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 🔗 إنشاء رابط مختصر - ينتهي بالدومين الأصلي
app.post('/api/shorten', async (req, res) => {
  const { url, customAlias } = req.body;

  if (!url) {
    return res.status(400).json({ error: 'الرابط مطلوب' });
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch {
    return res.status(400).json({ error: 'رابط غير صالح' });
  }

  let shortCode;

  // إذا المستخدم طلب اسم مخصص
  if (customAlias && customAlias.trim() !== '') {
    const aliasSlug = getSlug(customAlias.trim().toLowerCase());
    shortCode = `${aliasSlug}/${parsedUrl.hostname}`;
  } else {
    // إنشاء بادئة قصيرة + الدومين الكامل
    const prefix = generatePrefix();
    shortCode = `${prefix}/${parsedUrl.hostname}`;
  }

  // التحقق من عدم التكرار
  const existing = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (existing) {
    shortCode = `${shortCode}-${Math.floor(Math.random() * 900) + 100}`;
  }

  // حفظ الرابط
  db.run(
    'INSERT INTO links (short_code, original_url) VALUES (?, ?)',
    [shortCode, url]
  );

  const baseUrl = `${req.protocol}://${req.get('host')}`;
  res.json({
    shortUrl: `${baseUrl}/${shortCode}`,
    shortCode,
    originalUrl: url
  });
});

// دالة إنشاء بادئة قصيرة
function generatePrefix() {
  const prefixes = ['go', 'link', 'v', 'r', 'to', 'at', 'in', 'on'];
  return prefixes[Math.floor(Math.random() * prefixes.length)];
}

// 📊 لوحة التحكم
app.get('/api/dashboard', (req, res) => {
  const links = db.all(`
    SELECT l.id, l.short_code, l.original_url, l.created_at,
           COUNT(c.id) as clicks_count
    FROM links l
    LEFT JOIN clicks c ON c.link_id = l.id
    GROUP BY l.id
    ORDER BY l.created_at DESC
  `);
  res.json(links);
});

// 📈 تفاصيل نقرات رابط معين
app.get('/api/clicks/*', (req, res) => {
  const shortCode = req.params[0];
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [shortCode]);
  if (!link) {
    return res.status(404).json({ error: 'الرابط غير موجود' });
  }

  const clicks = db.all(`
    SELECT country, city, device_type, browser, os, lat, lng, clicked_at
    FROM clicks 
    WHERE link_id = ?
    ORDER BY clicked_at DESC
    LIMIT 100
  `, [link.id]);

  res.json({ link, clicks });
});

// 📝 تسجيل النقرة مع الموقع
app.post('/api/click', async (req, res) => {
  const { shortCode, deviceType, browser, os } = req.body;

  const link = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (!link) {
    return res.status(404).json({ error: 'رابط غير موجود' });
  }

  let ip = '';
  if (req.headers['x-forwarded-for']) {
    ip = req.headers['x-forwarded-for'].split(',')[0].trim();
  } else if (req.headers['x-real-ip']) {
    ip = req.headers['x-real-ip'].trim();
  } else {
    ip = req.ip || req.connection.remoteAddress;
  }

  ip = ip.replace('::ffff:', '');
  console.log('🔍 IP المستخدم:', ip);

  let country = null, city = null, lat = null, lng = null;

  try {
    const geoRes = await fetch(`http://ip-api.com/json/${ip}?fields=status,country,city,lat,lon`);
    const geoData = await geoRes.json();

    console.log('📍 بيانات الموقع:', JSON.stringify(geoData));

    if (geoData.status === 'success') {
      country = geoData.country;
      city = geoData.city;
      lat = geoData.lat;
      lng = geoData.lon;
      console.log('✅ الموقع:', country, city);
    }
  } catch (err) {
    console.error(' خطأ Geocoding:', err.message);
  }

  db.run(`
    INSERT INTO clicks (link_id, country, city, device_type, browser, os, lat, lng)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `, [link.id, country, city, deviceType, browser, os, lat, lng]);

  console.log('✅ تم حفظ النقرة');
  res.json({ success: true, location: { country, city, lat, lng } });
});

// 🎯 صفحة التتبع
app.get('/track.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'track.html'));
});

//  إعادة التوجيه - يقرأ المسار الكامل (wildcard)
app.get('/*', (req, res) => {
  const fullPath = req.params[0];
  
  // تجاهل المسارات الثابتة
  if (!fullPath || fullPath === 'track.html' || fullPath.startsWith('api/')) {
    return res.status(404).send('غير موجود');
  }

  const link = db.get('SELECT * FROM links WHERE short_code = ?', [fullPath]);
  
  if (!link) {
    return res.status(404).send(`
      <!DOCTYPE html>
      <html dir="rtl" lang="ar">
      <head>
        <meta charset="UTF-8">
        <title>رابط غير موجود</title>
        <style>
          body { font-family: Arial; text-align: center; padding: 50px; background: #f5f5f5; }
          .error { color: #e74c3c; font-size: 24px; }
          a { color: #3498db; }
        </style>
      </head>
      <body>
        <h1 class="error"> الرابط غير موجود</h1>
        <p>الرابط اللي تبحث عنه مو موجود أو تم حذفه</p>
        <a href="/">← رجوع للصفحة الرئيسية</a>
      </body>
      </html>
    `);
  }

  const ua = new UAParser(req.headers['user-agent']).getResult();
  const deviceType = ua.device.type || 'desktop';
  const browser = ua.browser.name || 'Unknown';
  const os = ua.os.name || 'Unknown';

  res.redirect(
    `/track.html?code=${encodeURIComponent(link.short_code)}` +
    `&url=${encodeURIComponent(link.original_url)}` +
    `&dt=${deviceType}` +
    `&br=${encodeURIComponent(browser)}` +
    `&os=${encodeURIComponent(os)}`
  );
});
