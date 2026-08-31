const express = require('express');
const fetch = require('node-fetch');
const { nanoid } = require('nanoid');
const UAParser = require('ua-parser-js');
const db = require('./database');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static('public'));

db.initDB().then(() => {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`✅ السيرفر شغّال على المنفذ ${PORT}`);
  });
}).catch(err => {
  console.error('❌ خطأ:', err);
  process.exit(1);
});

function encodeDomain(hostname) {
  return hostname.replace(/\./g, '-').replace(/\//g, '-');
}

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 🔗 إنشاء رابط مختصر
app.post('/api/shorten', async (req, res) => {
  const { url, customAlias } = req.body;

  if (!url) return res.status(400).json({ error: 'الرابط مطلوب' });

  let parsedUrl;
  try {
    parsedUrl = new URL(url);
  } catch {
    return res.status(400).json({ error: 'رابط غير صالح' });
  }

  const encodedDomain = encodeDomain(parsedUrl.hostname);
  let shortCode;

  if (customAlias && customAlias.trim() !== '') {
    shortCode = `${customAlias.trim().toLowerCase().replace(/\s+/g, '-')}-${encodedDomain}`;
  } else {
    const prefixes = ['go', 'link', 'v', 'r', 'to', 'at'];
    const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
    shortCode = `${prefix}-${encodedDomain}`;
  }

  const existing = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (existing) {
    shortCode = `${shortCode}-${Math.floor(Math.random() * 900) + 100}`;
  }

  db.run('INSERT INTO links (short_code, original_url) VALUES (?, ?)', [shortCode, url]);

  const baseUrl = `${req.protocol}://${req.get('host')}`;
  res.json({
    shortUrl: `${baseUrl}/${shortCode}`,
    shortCode,
    originalUrl: url
  });
});

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

// 📈 تفاصيل نقرات (مع IP)
app.get('/api/clicks/:shortCode', (req, res) => {
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [req.params.shortCode]);
  if (!link) return res.status(404).json({ error: 'غير موجود' });

  const clicks = db.all(`
    SELECT ip_address, country, city, device_type, browser, os, lat, lng, clicked_at
    FROM clicks WHERE link_id = ? ORDER BY clicked_at DESC LIMIT 100
  `, [link.id]);

  res.json({ link, clicks });
});

// 📝 تسجيل النقرة مع IP والموقع
app.post('/api/click', async (req, res) => {
  const { shortCode, deviceType, browser, os } = req.body;

  const link = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (!link) return res.status(404).json({ error: 'رابط غير موجود' });

  // الحصول على IP الحقيقي
  let ip = req.headers['x-forwarded-for']?.split(',')[0].trim() || 
           req.headers['x-real-ip'] || 
           req.ip || '';
  ip = ip.replace('::ffff:', '');

  console.log('🔍 IP:', ip);

  let country = null, city = null, lat = null, lng = null;

  try {
    const geoRes = await fetch(`http://ip-api.com/json/${ip}?fields=status,country,city,lat,lon`);
    const geoData = await geoRes.json();
    console.log('📍 Geo:', JSON.stringify(geoData));

    if (geoData.status === 'success') {
      country = geoData.country;
      city = geoData.city;
      lat = geoData.lat;
      lng = geoData.lon;
    }
  } catch (err) {
    console.error('❌ Geocoding error:', err.message);
  }

  // حفظ IP مع باقي البيانات
  db.run(`
    INSERT INTO clicks (link_id, ip_address, country, city, device_type, browser, os, lat, lng)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `, [link.id, ip, country, city, deviceType, browser, os, lat, lng]);

  console.log('✅ حفظ:', { ip, country, city, lat, lng });
  res.json({ success: true, ip, location: { country, city, lat, lng } });
});

app.get('/track.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'track.html'));
});

// 🔄 إعادة التوجيه
app.get('/:shortCode', (req, res) => {
  const shortCode = req.params.shortCode;
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [shortCode]);

  if (!link) {
    return res.status(404).send(`
      <!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>غير موجود</title>
      <style>body{font-family:Arial;text-align:center;padding:50px;background:#f5f5f5}
      .error{color:#e74c3c;font-size:24px}a{color:#3498db}</style></head>
      <body><h1 class="error">❌ الرابط غير موجود</h1>
      <p>الرابط اللي تبحث عنه مو موجود</p>
      <a href="/">← رجوع</a></body></html>
    `);
  }

  const ua = new UAParser(req.headers['user-agent']).getResult();
  const deviceType = ua.device.type || 'desktop';
  const browser = ua.browser.name || 'Unknown';
  const os = ua.os.name || 'Unknown';

  res.redirect(
    `/track.html?code=${encodeURIComponent(link.short_code)}` +
    `&url=${encodeURIComponent(link.original_url)}` +
    `&dt=${deviceType}&br=${encodeURIComponent(browser)}&os=${encodeURIComponent(os)}`
  );
});
