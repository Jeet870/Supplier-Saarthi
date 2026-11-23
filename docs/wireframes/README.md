# Supplier Saarthi: Wireframe Specifications (Task 1C-1 & 1C-3)

These wireframe photos represent the mobile interface for **Supplier Saarthi** (Wisperflow Hackathon 2026).
The design is optimized for Kirana shopkeepers on Android/iOS smartphones with large touch targets ($\ge 56\text{px}$), high contrast, and colloquial Hinglish terminology.

---

## 1. Screen Inventory & Visual Artifacts

| Screen # | Artifact Name | Description | Main Action | Tap Flow |
| :---: | :--- | :--- | :--- | :---: |
| **01** | `01-home.jpg` | **Home Screen:** High-contrast dashboard with summary count ("3 open items"), two dominant CTA buttons, and secondary quick links. | One tap enters flow | **Tap 1** |
| **02** | `02-delivery-check.jpg` | **Delivery Check:** Supplier picker, prominent microphone recording button, transcript box, fallback text box, and photo button. | Tap mic, speak | **Tap 2** |
| **03** | `03-promise-note.jpg` | **Promise Note:** Supplier picker, follow-up date selector, mic recording button, transcript box, and typed fallback. | Tap mic, speak | **Tap 2** |
| **04** | `04-confirmation.jpg` | **Confirmation Card:** Audio readback box (TTS), editable record fields, disclaimer note, and big "HAAN" & "GALAT HAI" buttons. | Review & tap HAAN | **Tap 3 (Saved!)** |
| **05** | `05-supplier-timeline.jpg` | **Supplier Timeline:** Chronological list of deliveries and promises for a specific supplier, status chips (`OPEN`, `RESOLVED`, `DISPUTED`), search filter, Mark Done, and WhatsApp Share. | Update status or share | View/Share |
| **06** | `06-pending.jpg` | **Pending Screen:** Cross-supplier overview of all actionable items with filter tabs for Deliveries and Promises. | Tap item to resolve | View/Filter |
| **07** | `07-states.jpg` | **App States:** Dedicated UI designs for Empty State ("Kuch pending nahi"), Loading ("Soch raha hoon..."), and Error ("Samajh nahi aaya, dobara bolo"). | User feedback | N/A |

---

## 2. Target Tap Flow Analysis (Target $\le 4$ Taps)

### Journey A: Delivery Discrepancy Flow
1. **Home Screen:** Tap *"Delivery Check"* button (**Tap 1**).
2. **Delivery Screen:** Tap *"Mic"* button and speak sentence (**Tap 2**).
3. **Confirmation Screen:** Listen to audio readback, review editable fields, and tap *"HAAN"* (**Tap 3**).
* **Total Taps:** **3 taps** ($\le 4$ target met).

### Journey B: Supplier Promise Flow
1. **Home Screen:** Tap *"Promise Note"* button (**Tap 1**).
2. **Promise Screen:** Tap *"Mic"* button and speak promise (**Tap 2**).
3. **Confirmation Screen:** Review promise fields & date, tap *"HAAN"* (**Tap 3**).
* **Total Taps:** **3 taps** ($\le 4$ target met).

---

## 3. Kirana-Friendly Design Principles
* **Thumb-friendly Targets:** All primary buttons are minimum $56\text{px}$ in height with rounded pill corners.
* **Bilingual Clarity:** English functional terms paired with familiar Hindi/Hinglish vocabulary (*"Haan"*, *"Galat hai"*, *"Vyapari"*, *"Wada"*, *"Baqaya"*).
* **Defensive Confirmation:** No record is committed without the shopkeeper explicitly confirming via the green **Haan** button.
* **Legal Disclaimer:** Prominent note on confirmation: *"Yeh ek record hai, kanooni saboot nahi."*
