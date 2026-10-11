# Kishan-bagh

**Kishan Bagh Call** lets you make voice calls with **no Wi-Fi internet and no mobile data**.
It comes in two versions:

| | Android app (`android/`) | Web app (`web/`) |
|---|---|---|
| How phones connect | Directly phone-to-phone over Bluetooth, BLE and Wi-Fi Direct | Through one phone's hotspot or a Wi-Fi router that has no internet |
| Needs a router or hotspot? | No | Yes (internet is not needed) |
| Range | About 10–100 m, depending on walls and the phones | Anywhere the hotspot or router reaches |
| Works on | Android 7.0+ with Google Play services | Any modern browser (Android, iPhone, laptop) |

---

## Android app: phone-to-phone

Both phones run the app. Neither phone needs a SIM, internet or a router.

1. Install the app on both phones (see *Building* below).
2. Open the app, type your name and tap **Go online**. Allow the Microphone, Nearby devices
   and Bluetooth permissions. On Android 11 and older, also turn on Location.
3. The other phone's name appears in the list. Tap it to call.
4. The other phone rings and shows **Answer / Decline**.
5. During a call you can use **Mute**, **Speaker** and **End call**.

How it works: Google [Nearby Connections](https://developers.google.com/nearby/connections/overview)
finds the other phone over Bluetooth and then upgrades to Wi-Fi Direct when it can.
Each phone streams its microphone (16 kHz voice audio, with echo cancelling) straight to the other.

### Building the APK

You need internet once, to download the build tools.

- **Android Studio:** *File → Open* the `android/` folder, then *Run*, or use
  *Build → Build APK(s)*.
- **Command line:** with the Android SDK installed (set `ANDROID_HOME`), run
  ```
  cd android
  ./gradlew assembleDebug
  ```
  The APK is written to `android/app/build/outputs/apk/debug/app-debug.apk`.
  Copy it to the phones and install it.

---

## Web app: over a hotspot with no internet

One device (a laptop, or an Android phone running [Termux](https://termux.dev)) runs a small
server. Everyone else just opens a web page.

1. **One time, while you have internet:** install [Node.js](https://nodejs.org) 18+, then run
   ```
   cd web
   npm install
   ```
2. Turn on a phone hotspot with mobile data **off**, or use a Wi-Fi router with no internet.
   Connect every device to it, including the server.
3. On the server, run:
   ```
   cd web
   npm start
   ```
   It prints addresses like `https://192.168.43.5:8443`.
4. On each phone, open that address in Chrome or Safari. The browser warns that the connection
   is "not private", because the server uses its own certificate (needed for microphone
   access). Tap **Advanced → Proceed**.
5. Enter your name and tap **Go online**. Tap **Call** next to someone's name; they tap **Answer**.

The server only sets up calls. Audio goes directly between the two devices (WebRTC), and no
internet servers are used at any point.

Run the automated test (two headless browsers make a call to each other):
```
cd web
npm test
```
