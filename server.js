const express = require('express');
const { nanoid } = require('nanoid');
const UAParser = require('ua-parser-js');
const db = require('./database');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static('public'));

// 🏠 الصفحة الرئيسية
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 🔗 إنشاء رابط قصير
app.post('/api/shorten', (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: 'الرابط مطلوب' });

  try {
    new URL(url); // تحقق من صيغة الرابط
  } catch {
    return res.status(400).json({ error: 'رابط غير صالح' });
  }

  const shortCode = nanoid(7);
  const stmt = db.prepare('INSERT INTO links (short_code, original_url) VALUES (?, ?)');
  stmt.run(shortCode, url);

  const baseUrl = `${req.protocol}://${req.get('host')}`;
  res.json({
    shortUrl: `${baseUrl}/${shortCode}`,
    shortCode
  });
});

// 📊 لوحة التحكم - كل الروابط
app.get('/api/dashboard', (req, res) => {
  const links = db.prepare(`
    SELECT l.id, l.short_code, l.original_url, l.created_at,
           COUNT(c.id) as clicks_count
    FROM links l
    LEFT JOIN clicks c ON c.link_id = l.id
    GROUP BY l.id
    ORDER BY l.created_at DESC
  `).all();
  res.json(links);
});

// 📈 تفاصيل نقرات رابط معين
app.get('/api/clicks/:shortCode', (req, res) => {
  const link = db.prepare('SELECT * FROM links WHERE short_code = ?').get(req.params.shortCode);
  if (!link) return res.status(404).json({ error: 'غير موجود' });

  const clicks = db.prepare(`
    SELECT country, city, device_type, browser, os, lat, lng, clicked_at
    FROM clicks WHERE link_id = ?
    ORDER BY clicked_at DESC
  `).all(link.id);

  res.json({ link, clicks });
});

// 📝 تسجيل النقرة (تُستدعى من صفحة redirect.html)
app.post('/api/click', (req, res) => {
  const { shortCode, country, city, deviceType, browser, os, lat, lng } = req.body;

  const link = db.prepare('SELECT id FROM links WHERE short_code = ?').get(shortCode);
  if (!link) return res.status(404).json({ error: 'رابط غير موجود' });

  db.prepare(`
    INSERT INTO clicks (link_id, country, city, device_type, browser, os, lat, lng)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(link.id, country || null, city || null, deviceType, browser, os, lat || null, lng || null);

  res.json({ success: true });
});

// 🚀 إعادة التوجيه
app.get('/:shortCode', (req, res) => {
  const link = db.prepare('SELECT * FROM links WHERE short_code = ?').get(req.params.shortCode);
  if (!link) return res.status(404).send('الرابط غير موجود');

  // نمرر بيانات User-Agent عبر query للصفحة الوسيطة
  const ua = new UAParser(req.headers['user-agent']).getResult();
  const deviceType = ua.device.type || 'desktop';
  const browser = ua.browser.name || 'Unknown';
  const os = ua.os.name || 'Unknown';

  res.sendFile(path.join(__dirname, 'public', 'redirect.html'));
  // نمرر البيانات عبر meta tags (يقرأها JS في redirect.html)
  // بديل أبسط: نستخدم query params
  res.redirect(`/redirect.html?code=${link.short_code}&url=${encodeURIComponent(link.original_url)}&dt=${deviceType}&br=${encodeURIComponent(browser)}&os=${encodeURIComponent(os)}`);
});

app.listen(3000, () => console.log('✅ شغّال على http://localhost:3000'));
