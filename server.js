const express = require("express");
const cors = require("cors");
const mysql = require("mysql2");
const multer = require("multer");
const fs = require("fs");
const axios = require("axios");
const nodemailer = require("nodemailer");
const FormData = require("form-data");

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static("frontend"));

/* ================= DATABASE ================= */
const db = mysql.createConnection({
  host: "localhost",
  user: "root",
  password: "Aditya@8",   // 🔴 change if needed
  database: "ids_db"
});

db.connect(err => {
  if (err) {
    console.error("❌ DB ERROR:", err);
    process.exit(1);
  }
  console.log("✅ MySQL Connected");

  // ✅ Auto-create users table if it doesn't exist
  db.query(`
    CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      username VARCHAR(100) NOT NULL UNIQUE,
      password VARCHAR(255) NOT NULL,
      role ENUM('user', 'admin') DEFAULT 'user',
      created_at DATETIME DEFAULT NOW()
    )
  `, err => {
    if (err) console.error("❌ Table creation error:", err);
    else console.log("✅ users table ready");
  });

  // ✅ Auto-create uploads table if it doesn't exist
  db.query(`
    CREATE TABLE IF NOT EXISTS uploads (
      id INT AUTO_INCREMENT PRIMARY KEY,
      username VARCHAR(100),
      filename VARCHAR(255),
      prediction VARCHAR(50),
      confidence FLOAT,
      status VARCHAR(50) DEFAULT 'Pending',
      uploaded_at DATETIME DEFAULT NOW()
    )
  `, err => {
    if (err) console.error("❌ uploads table error:", err);
    else console.log("✅ uploads table ready");
  });
});

/* ================= EMAIL (GMAIL SMTP) ================= */
const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: "",   // 🔴 your Gmail address
    pass: ""    // 🔴 your Gmail App Password (not your real password)
  }
});

/* ================= UPLOAD (MULTER) ================= */
if (!fs.existsSync("uploads")) fs.mkdirSync("uploads");

const storage = multer.diskStorage({
  destination: "uploads/",
  filename: (req, file, cb) =>
    cb(null, Date.now() + "_" + file.originalname)
});

const upload = multer({ storage });

/* ================= ROUTES ================= */

/* 📝 REGISTER  ← THIS WAS MISSING - NOW FIXED */
app.post("/register", (req, res) => {
  const { username, password, role } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: "Username and password are required" });
  }

  // Check if username already exists
  db.query(
    "SELECT id FROM users WHERE username = ?",
    [username],
    (err, rows) => {
      if (err) {
        console.error("REGISTER CHECK ERROR:", err);
        return res.status(500).json({ error: "Server error" });
      }

      if (rows.length > 0) {
        // Username taken → 409 Conflict → frontend shows "Username already exists"
        return res.status(409).json({ error: "Username already exists" });
      }

      // Insert new user
      db.query(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        [username, password, role || "user"],
        (err) => {
          if (err) {
            console.error("REGISTER INSERT ERROR:", err);
            return res.status(500).json({ error: "Registration failed" });
          }
          console.log("✅ New user registered:", username);
          res.status(201).json({ message: "Account created successfully" });
        }
      );
    }
  );
});

/* 🔐 LOGIN */
app.post("/login", (req, res) => {
  const { username, password, role } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: "Username and password required" });
  }

  // Check DB first
  db.query(
    "SELECT * FROM users WHERE username = ? AND password = ?",
    [username, password],
    (err, rows) => {
      if (err) {
        console.error("LOGIN DB ERROR:", err);
        return res.status(500).json({ error: "Server error" });
      }

      if (rows.length > 0) {
        const user = rows[0];
        // If role is specified, enforce it
        if (role && user.role !== role) {
          return res.status(401).json({ error: "Invalid credentials" });
        }
        return res.json({ username: user.username, role: user.role });
      }

      // Fallback: hardcoded admin (optional — remove if not needed)
      const hardcoded = [
        { username: "admin", password: "admin123", role: "admin" },
      ];
      const match = hardcoded.find(
        u => u.username === username && u.password === password
      );
      if (match && (!role || match.role === role)) {
        return res.json(match);
      }

      return res.status(401).json({ error: "Invalid credentials" });
    }
  );
});

/* 📤 USER UPLOAD */
app.post("/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const username = req.body.username || "user";

    // Save upload in DB
    db.query(
      "INSERT INTO uploads (username, filename, status, uploaded_at) VALUES (?, ?, 'Pending', NOW())",
      [username, req.file.filename]
    );

    // Send file to Flask
    const formData = new FormData();
    formData.append("file", fs.createReadStream(req.file.path));

    await axios.post("http://localhost:5001/upload", formData, {
      headers: formData.getHeaders(),
      timeout: 20000
    });

    res.json({ message: "File uploaded & sent to ML backend" });

  } catch (err) {
    console.error("UPLOAD ERROR:", err.message);
    res.status(500).json({ error: "Upload failed" });
  }
});

/* 📁 ADMIN – FETCH ALL UPLOADS */
app.get("/admin/uploads", (req, res) => {
  db.query(
    `SELECT id, username, filename, prediction, confidence, status, uploaded_at
     FROM uploads ORDER BY uploaded_at DESC`,
    (err, rows) => {
      if (err) {
        console.error("ADMIN UPLOADS ERROR:", err);
        return res.json([]);
      }
      res.json(rows);
    }
  );
});

/* 👁️ ADMIN – VIEW FILE + RUN PREDICTION */
app.get("/admin/file/:id", async (req, res) => {
  try {
    const flaskRes = await axios.get("http://localhost:5001/predict", {
      timeout: 20000
    });
    const data = flaskRes.data;
    const prediction = data.attacks_detected > data.normal_detected ? "Attack" : "Normal";
    const confidence = data.attacks_detected / data.total_records;

    db.query(
      "UPDATE uploads SET prediction=?, confidence=?, status='Analyzed' WHERE id=?",
      [prediction, confidence, req.params.id]
    );

    res.json({ prediction, confidence });

  } catch (err) {
    console.error("ADMIN VIEW ERROR:", err.message);
    res.status(500).json({ error: "Prediction unavailable" });
  }
});

/* 🔍 USER DASHBOARD – RUN DETECTION */
app.get("/predict", async (req, res) => {
  try {
    const response = await axios.get("http://localhost:5001/predict", {
      timeout: 20000
    });
    res.json(response.data);
  } catch (err) {
    console.error("PREDICT ERROR:", err.message);
    res.status(500).json({ error: "Prediction failed" });
  }
});

/* ================= START ================= */
app.listen(5000, () => {
  console.log("🚀 IDS Backend running on http://localhost:5000");
  console.log("✅ Routes: /register  /login  /upload  /predict  /admin/uploads");
});