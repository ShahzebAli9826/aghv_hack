# 🛡️ Aegis Auth UI — Developer & User Guide

A production-grade, SaaS-level mobile authentication screen built with **React Native**, **Expo**, and **TypeScript** for the Aegis Flood Detection & Response System.

---

## 📁 1. Asset Storage & Locations

All primary visual assets are saved in two organized locations:

| Asset Name | Description | Path |
| :--- | :--- | :--- |
| **`flood-auth-background.png`** | High-resolution background featuring lake water, flooded home, mountain horizon, water drop logo, and "Welcome Back!" text | [`assets/auth_ui_assets/flood-auth-background.png`](file:///c:/Users/rawal/Desktop/app/assets/auth_ui_assets/flood-auth-background.png) <br> [`dell-flood-app/assets/flood-auth-background.png`](file:///c:/Users/rawal/Desktop/app/dell-flood-app/assets/flood-auth-background.png) |
| **`google-sign-in.png`** | Official Google 'G' icon for social authentication button | [`assets/auth_ui_assets/google-sign-in.png`](file:///c:/Users/rawal/Desktop/app/assets/auth_ui_assets/google-sign-in.png) <br> [`dell-flood-app/assets/google-sign-in.png`](file:///c:/Users/rawal/Desktop/app/dell-flood-app/assets/google-sign-in.png) |
| **`apple-sign-in.png`** | Official Apple logo for social authentication button | [`assets/auth_ui_assets/apple-sign-in.png`](file:///c:/Users/rawal/Desktop/app/assets/auth_ui_assets/apple-sign-in.png) <br> [`dell-flood-app/assets/apple-sign-in.png`](file:///c:/Users/rawal/Desktop/app/dell-flood-app/assets/apple-sign-in.png) |

---

## 🚀 2. How to Run & View the UI

### Option A: On Any Mobile Phone (Recommended for Judges & Live Demos)
> **No app installation needed!** Runs instantly in Safari, Chrome, or any mobile browser.

1. Connect your laptop and phone to the same **Wi-Fi** or your phone's **Mobile Hotspot**.
2. Start the Expo web server from your laptop terminal:
   ```bash
   cd dell-flood-app
   npx expo start --web
   ```
3. Open the browser on your phone and navigate to:
   ```
   http://<YOUR_LAPTOP_IP>:8081
   ```
   *(e.g., `http://192.168.0.171:8081`)*
4. The full-screen mobile app UI loads immediately with touch interactions enabled.

---

### Option B: On Desktop / Laptop (Chrome DevTools Mobile Simulation)
To preview and test the mobile UI directly on your computer:

1. Open `http://localhost:8081` in Google Chrome.
2. Press **F12** (or right-click → **Inspect**).
3. Press **Ctrl + Shift + M** (or click the device toggle icon at the top-left of DevTools).
4. Select **iPhone 14 Pro** or **Pixel 7** from the top dimensions dropdown.

---

### Option C: Native Mobile via Expo Go
To test native gestures, vibration, and push notifications on physical devices:

1. Install **Expo Go** from [Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent) or [Apple App Store](https://apps.apple.com/app/expo-go/id982107779).
2. Run with tunnel mode:
   ```bash
   npx expo start --tunnel
   ```
3. Scan the terminal QR code with your phone camera or the Expo Go app.

---

## 🎨 3. Key Interactive Features & UX Flow

```
+-------------------------------------------------------+
|  (<-)  [Top-Left Arrow]              [Sky Area]       |
|                                                       |
|                       [💧 AEGIS]                       |
|                   Flood Detection System              |
|                                                       |
|                     Welcome Back!                     |
|           We're here to keep your community safe.     |
|                   Sign in to continue.                |
|                                                       |
|      +-----------------------------------------+      |
|      |               ___ (Handle)              |      |
|      |                ^  (Chevron)             |      |
|      |                                         |      |
|      |             Secure sign in              |      |
|      |      Access your response workspace     |      |
|      |                                         |      |
|      |  [ Email: you@example.com           ]   |      |
|      |  [ Password: ••••••••          (👁) ]   |      |
|      |                                         |      |
|      |  [x] Remember me       Forgot Password? |      |
|      |                                         |      |
|      |  [============ LOG IN ============]    |      |
|      |                                         |      |
|      |  --------- or continue with ----------  |      |
|      |  [ G Google ]          [  Apple ]     |      |
|      |                                         |      |
|      |       Don't have an account? Sign Up    |      |
|      |                                         |      |
|      |       ⚙️ Server Connection Settings     |      |
|      +-----------------------------------------+      |
|                                                       |
|  [~~~~~~~~~~~~~~~~~ Lake Water ~~~~~~~~~~~~~~~~~~~~]  |
+-------------------------------------------------------+
```

### 1. One-Tap Pull-Up Handle & Auto-Scroll
- **Tappable Handle Bar & Chevron**: Tap the small gray bar or chevron arrow at the top of the card.
- **Auto-Scroll**: Tapping smoothly slides the card upward, revealing all form fields without needing manual drag.
- **Dynamic Arrow**: The chevron arrow automatically disappears when the card is pulled up, leaving a clean handle bar. Tapping again slides it back down.

### 2. Top-Left Navigation Button `(←)`
- Situated in the clear sky area (`top: -150, left: 4` relative to the card).
- **Never overlaps** "Welcome Back!" or the AEGIS logo.
- When on **Sign In**, tapping switches to **Sign Up** mode.
- When on **Sign Up**, tapping switches back to **Sign In** mode.

### 3. Floating Card with 4 Rounded Corners & Bottom Margin
- Styled with `borderRadius: 32` on all 4 corners and `marginBottom: 40`.
- Floats over the water scenery with generous breathing room, never touching the screen edge or Android/iOS system navigation bar.

### 4. Role Selector (Citizen vs. Official)
- On the **Sign Up** screen, users can select between:
  - 👥 **Public Citizen**: Standard community reporting and flood map viewing.
  - 🛡️ **Gov Official**: Access to NDRF/SDRF deployment and emergency broadcast tools.

### 5. Configurable Backend URL
- Tap **⚙️ Server Connection Settings** at the bottom of the card.
- Allows switching between local development (`http://localhost:8000/api`), remote IP (`http://192.168.0.171:8000/api`), or production cloud URL.

---

## 💻 4. How to Reuse in Another React Native / Expo Project

### Required Dependencies
```bash
npx expo install expo-linear-gradient
npm install lucide-react-native
```

### Import Statement
```tsx
import { StyleSheet, View, Text, TextInput, TouchableOpacity, ScrollView, ImageBackground, Image } from 'react-native';
import { Mail, Lock, Eye, EyeOff, ChevronUp, ArrowLeft, Settings } from 'lucide-react-native';
import { LinearGradient } from 'expo-linear-gradient';
```

### Asset Reference
```tsx
const BG_IMAGE = require('./assets/flood-auth-background.png');
const GOOGLE_ICON = require('./assets/google-sign-in.png');
const APPLE_ICON = require('./assets/apple-sign-in.png');
```

---

## 🏆 Presentation Tips for Hackathon Pitches
- **Demo on Phone**: Show judges the live web link on your or their phone. It proves cross-platform execution.
- **Show the Animation**: Tap the top chevron arrow to demonstrate the smooth card pull-up.
- **Highlight Detail**: Point out the password visibility toggle, role selector, and branded Google/Apple buttons.
