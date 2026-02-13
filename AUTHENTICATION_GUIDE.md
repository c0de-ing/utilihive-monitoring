# Authentication Setup Guide

The dashboard now includes login authentication to protect access.

---

## 🔐 Default Credentials (Local Development)

**Username:** `admin`
**Password:** `admin`

**⚠️ IMPORTANT:** Change these before deploying!

---

## 🚀 For Streamlit Cloud Deployment

### **Setup Secure Credentials:**

1. **Go to your Streamlit Cloud app**
2. **Click** Settings (⚙️) → **Secrets**
3. **Add** the following in TOML format:

```toml
[credentials]
[credentials.users]
admin = "your_secure_password_here"
user1 = "another_password"
user2 = "yet_another_password"
```

4. **Click** "Save"

### **Example with multiple users:**

```toml
[credentials]
[credentials.users]
admin = "SuperSecure123!"
jfurrer = "MyPassword456"
viewer = "ReadOnly789"
```

---

## 💻 For Local Development

### **Option 1: Use Default (Quick Testing)**
- Just run the dashboard
- Login with `admin` / `admin`

### **Option 2: Create Streamlit Secrets Locally**

Create `.streamlit/secrets.toml` in your project:

```bash
mkdir .streamlit
```

Create/edit `.streamlit/secrets.toml`:

```toml
[credentials]
[credentials.users]
admin = "your_local_password"
developer = "dev_password"
```

**Note:** `.streamlit/secrets.toml` is automatically excluded by `.gitignore`

---

## 🔧 How It Works

1. **User visits dashboard** → Login page appears
2. **User enters credentials** → Password is hashed (SHA-256)
3. **System checks** against configured users
4. **If valid** → Access granted, session stored
5. **If invalid** → Error message shown

### **Security Features:**
- ✅ Passwords are hashed (never stored in plain text)
- ✅ Session-based authentication
- ✅ Logout functionality
- ✅ Credentials stored in secrets (not in code)
- ✅ Different credentials for dev/prod

---

## 👥 Managing Users

### **Add a New User:**

In Streamlit Cloud secrets:
```toml
[credentials.users]
existing_user = "password1"
new_user = "password2"      # Add this line
```

### **Remove a User:**

Simply delete their line from the secrets.

### **Change a Password:**

Update the password value:
```toml
[credentials.users]
admin = "new_secure_password"
```

---

## 🧪 Testing Authentication

### **Test Login:**
1. Run dashboard: `streamlit run dashboard_v3.py`
2. You'll see the login page
3. Enter username and password
4. Click "Login"

### **Test Logout:**
1. After logging in, check sidebar
2. You'll see your username
3. Click "🚪 Logout" button
4. You'll be returned to login page

---

## 🔒 Security Best Practices

### **DO:**
- ✅ Use strong, unique passwords
- ✅ Change default credentials immediately
- ✅ Use different passwords for different environments
- ✅ Keep secrets in Streamlit Cloud secrets (not in code)
- ✅ Review who has access regularly

### **DON'T:**
- ❌ Use simple passwords like "password" or "123456"
- ❌ Commit passwords to git
- ❌ Share credentials via email/chat
- ❌ Reuse passwords across systems
- ❌ Leave default credentials in production

---

## 🌐 Streamlit Cloud - Additional Security

Streamlit Cloud also offers:

1. **App Visibility:**
   - Private apps (requires Streamlit account to access)
   - Public apps (anyone with URL can access)

2. **GitHub Repository Visibility:**
   - Keep repo private for sensitive apps

3. **IP Whitelisting:**
   - Available in paid plans

---

## 🆘 Troubleshooting

### "Username or password incorrect"
- **Check:** Username and password spelling
- **Check:** Secrets are properly formatted (TOML syntax)
- **Try:** Clear browser cache and try again

### Can't login locally
- **Check:** `.streamlit/secrets.toml` exists and has correct format
- **Try:** Use default credentials (admin/admin)
- **Check:** No syntax errors in secrets.toml

### Logged out unexpectedly
- **Reason:** Streamlit app restarted or session expired
- **Solution:** Just login again

### Need to reset everything
- **Local:** Delete `.streamlit/secrets.toml`
- **Cloud:** Update secrets in Streamlit Cloud settings

---

## 📝 Example secrets.toml

Complete example:

```toml
# .streamlit/secrets.toml

# Authentication credentials
[credentials]
[credentials.users]
admin = "SuperSecure2024!"
analyst = "DataView2024"
readonly = "ViewOnly123"

# Optional: API tokens
[tokens]
api_token = "your_api_token_here"
```

---

## 🎯 Quick Start Checklist

- [ ] Dashboard installed and working
- [ ] Tested login with default credentials
- [ ] Created `.streamlit/secrets.toml` (local)
- [ ] Changed default passwords
- [ ] Added user accounts needed
- [ ] Tested all user logins
- [ ] Configured Streamlit Cloud secrets (if deploying)
- [ ] Tested logout functionality
- [ ] Documented credentials securely (password manager)

---

## 🔗 Additional Resources

- [Streamlit Secrets Documentation](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)
- [TOML Format Guide](https://toml.io/en/)
- [Password Best Practices](https://www.nist.gov/blogs/taking-measure/easy-ways-build-better-p5w0rd)

---

**Remember:** Security is only as strong as your weakest password! 🔐
