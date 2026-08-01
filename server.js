const express = require('express');
const { nanoid } = require('nanoid');
const UAParser = require('ua-parser-js');
const fetch = require('node-fetch');
const path = require('path');
const db = require('./database');

const app = express();
app.use(express.json());
app.use(express.static('public'));

// تهيئة قاعدة البيانات ثم تشغيل السيرفر
db.initDB().then(() => {
  app.listen(process.env.PORT || 3000, () => {
    console.log('✅ شغّال على المنفذ', process.env.PORT || 3000);
  });
}).catch(err => {
  console.error('❌ فشل تهيئة قاعدة البيانات:', err);
  process.exit(1);
});

// 🏠 الصفحة الرئيسية
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

//  لوحة التحكم
app.get('/dashboard.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

// 🔗 إنشاء رابط قصير
app.post('/api/shorten', (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: 'الرابط مطلوب' });

  try {
    new URL(url);
  } catch {
    return res.status(400).json({ error: 'رابط غير صالح' });
  }

  const shortCode = nanoid(7);
  db.run('INSERT INTO links (short_code, original_url) VALUES (?, ?)', [shortCode, url]);

  const baseUrl = `${req.protocol}://${req.get('host')}`;
  res.json({
    shortUrl: `${baseUrl}/${shortCode}`,
    shortCode
  });
});

// 📊 جلب كل الروابط مع عدد النقرات
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

//  تفاصيل نقرات رابط معين
app.get('/api/clicks/:shortCode', (req, res) => {
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [req.params.shortCode]);
  if (!link) return res.status(404).json({ error: 'غير موجود' });

  const clicks = db.all(`
    SELECT country, city, device_type, browser, os, lat, lng, clicked_at
    FROM clicks WHERE link_id = ?
    ORDER BY clicked_at DESC
  `, [link.id]);

  res.json({ link, clicks });
});

// 📝 تسجيل النقرة + الحصول على الموقع من IP (بدون إذن)
app.post('/api/click', async (req, res) => {
  const { shortCode, deviceType, browser, os } = req.body;

  const link = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (!link) return res.status(404).json({ error: 'رابط غير موجود' });

  // الحصول على IP الحقيقي
  const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.ip;

  let country = null, city = null, lat = null, lng = null;

  try {
    const geoRes = await fetch(`http://ip-api.com/json/${ip}?fields=status,country,city,lat,lon`);
    const geoData = await geoRes.json();

    if (geoData.status === 'success') {
      country = geoData.country;
      city = geoData.city;
      lat = geoData.lat;
      lng = geoData.lon;
    }
  } catch (err) {
    console.error('خطأ في تحديد الموقع:', err.message);
  }

  db.run(`
    INSERT INTO clicks (link_id, country, city, device_type, browser, os, lat, lng)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `, [link.id, country, city, deviceType, browser, os, lat, lng]);

  res.json({ success: true });
});

// 🚀 صفحة إعادة التوجيه الوسيطة
app.get('/redirect.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'redirect.html'));
});

// 🔄 معالجة الروابط القصيرة
app.get('/:shortCode', (req, res) => {
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [req.params.shortCode]);
  if (!link) return res.status(404).send('الرابط غير موجود');

  const ua = new UAParser(req.headers['user-agent']).getResult();
  const deviceType = ua.device.type || 'desktop';
  const browser = ua.browser.name || 'Unknown';
  const os = ua.os.name || 'Unknown';

  res.redirect(
    `/redirect.html?code=${link.short_code}` +
    `&url=${encodeURIComponent(link.original_url)}` +
    `&dt=${deviceType}` +
    `&br=${encodeURIComponent(browser)}` +
    `&os=${encodeURIComponent(os)}`
  );
});
