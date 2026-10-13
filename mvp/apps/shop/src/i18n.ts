import { createContext, useContext } from "react";
import type { Lang } from "./lang";

/**
 * Every label in the shop, in English and Hindi. `{name}` style placeholders are filled by `t()`.
 * (The Hindi is for native-speaker review, like the assistant's prompts.)
 */
const DICT = {
  // generic
  back: { en: "Back", hi: "पीछे" },
  close: { en: "Close", hi: "बंद करें" },
  cancel: { en: "Cancel", hi: "रद्द करें" },
  demo: { en: "Demo", hi: "डेमो" },
  loading: { en: "Loading…", hi: "लोड हो रहा है…" },
  tryAgain: { en: "Try again", hi: "फिर कोशिश करें" },
  seeAll: { en: "See all", hi: "सब देखें" },
  itemCount: { en: "{n} items", hi: "{n} सामान" },
  itemCount1: { en: "1 item", hi: "1 सामान" },
  orderByTalking: { en: "Order by talking", hi: "बोलकर ऑर्डर करें" },
  mainNav: { en: "Main", hi: "मुख्य" },
  chooseLanguage: { en: "Choose language", hi: "भाषा चुनें" },

  // nav
  navHome: { en: "Home", hi: "होम" },
  navBrowse: { en: "Browse", hi: "ब्राउज़" },
  navTalk: { en: "Talk", hi: "बोलिए" },
  navCart: { en: "Cart", hi: "कार्ट" },
  navOrders: { en: "Orders", hi: "ऑर्डर" },

  // home
  deliveryEyebrow: { en: "Delivery today or tomorrow", hi: "आज या कल डिलीवरी" },
  searchPlaceholder: { en: "Search atta, milk, eggs", hi: "आटा, दूध, अंडे खोजें" },
  accountSettings: { en: "Account and settings", hi: "खाता और सेटिंग" },
  changeAddress: { en: "Change delivery address", hi: "डिलीवरी का पता बदलें" },
  promoFreshEyebrow: { en: "Fresh produce", hi: "ताज़ा सामान" },
  promoFreshHead: { en: "Fruit and veg, picked fresh", hi: "ताज़े फल और सब्ज़ियाँ" },
  promoFreshCta: { en: "Shop now", hi: "अभी देखें" },
  promoTalkHead: { en: "Just say it. We fill the cart.", hi: "बस बोलिए। कार्ट हम भरेंगे।" },
  promoTalkCta: { en: "Try it now", hi: "अभी आज़माइए" },
  promoDairyEyebrow: { en: "Breakfast sorted", hi: "नाश्ता तैयार" },
  promoDairyHead: { en: "Milk, curd and butter", hi: "दूध, दही और मक्खन" },
  promoDairyCta: { en: "Shop dairy", hi: "डेयरी देखें" },
  shopByCategory: { en: "Shop by category", hi: "श्रेणी के अनुसार खरीदें" },
  buyAgain: { en: "Buy it again", hi: "फिर से मँगवाएँ" },
  popular: { en: "Popular picks", hi: "लोकप्रिय सामान" },
  freshVeg: { en: "Fresh fruit and veg", hi: "ताज़े फल और सब्ज़ियाँ" },
  yourShopkeeper: { en: "Your shopkeeper", hi: "आपका दुकानदार" },

  // categories
  catAll: { en: "All", hi: "सभी" },
  catAllProducts: { en: "All products", hi: "सभी सामान" },
  cat_dairy: { en: "Dairy", hi: "डेयरी" },
  cat_flours: { en: "Atta and flours", hi: "आटा और मैदा" },
  cat_staples: { en: "Rice, dal and oil", hi: "चावल, दाल और तेल" },
  cat_biscuits: { en: "Biscuits", hi: "बिस्कुट" },
  cat_snacks: { en: "Snacks", hi: "नाश्ता" },
  cat_beverages: { en: "Drinks", hi: "पेय" },
  cat_spices: { en: "Spices", hi: "मसाले" },
  cat_baking: { en: "Baking", hi: "बेकिंग" },
  cat_produce: { en: "Fruit and veg", hi: "फल और सब्ज़ी" },
  cat_home: { en: "Home", hi: "घर का सामान" },

  // list
  resultsFor: { en: '{n} results for "{q}"', hi: '"{q}" के {n} नतीजे' },
  resultFor: { en: '1 result for "{q}"', hi: '"{q}" का 1 नतीजा' },
  categoryCount: { en: "{cat} · {n} items", hi: "{cat} · {n} सामान" },
  nothingFound: { en: "Nothing found", hi: "कुछ नहीं मिला" },
  nothingFoundHint: {
    en: "Try milk, atta, eggs or biscuits. Or just say what you want.",
    hi: "दूध, आटा, अंडे या बिस्कुट खोजिए। या बस बोलकर बताइए।",
  },
  askShopkeeper: { en: "Ask the shopkeeper", hi: "दुकानदार से पूछें" },
  showMore: { en: "Show more", hi: "और दिखाइए" },
  loadError: { en: "Could not load products.", hi: "सामान लोड नहीं हो पाया।" },

  // product card / detail
  add: { en: "ADD", hi: "डालें" },
  addTo: { en: "Add {name}", hi: "{name} डालें" },
  removeOne: { en: "Remove one {name}", hi: "एक {name} हटाएँ" },
  addOne: { en: "Add one more {name}", hi: "एक और {name} डालें" },
  details: { en: "{name}, details", hi: "{name}, जानकारी" },
  outOfStock: { en: "Out of stock", hi: "अभी उपलब्ध नहीं" },
  addToCart: { en: "Add to cart", hi: "कार्ट में डालें" },
  inCart: { en: "{n} in cart", hi: "कार्ट में {n}" },
  packSize: { en: "Pack size", hi: "पैक" },
  inclTaxes: { en: "Inclusive of all taxes", hi: "सभी करों सहित" },
  productDetails: { en: "Product details", hi: "उत्पाद की जानकारी" },
  rowBrand: { en: "Brand", hi: "ब्रांड" },
  rowPack: { en: "Pack", hi: "पैक" },
  rowCategory: { en: "Category", hi: "श्रेणी" },
  rowAbout: { en: "About", hi: "विवरण" },
  rowUsage: { en: "How to use", hi: "इस्तेमाल" },
  similar: { en: "You might also like", hi: "ये भी पसंद आएँगे" },
  imageCredit: { en: "Photo: {credit}", hi: "फ़ोटो: {credit}" },
  openCart: { en: "Open cart", hi: "कार्ट खोलें" },
  viewCart: { en: "View cart", hi: "कार्ट देखें" },

  // cart
  cartTitle: { en: "Cart", hi: "कार्ट" },
  cartSub: { en: "{count} · slot chosen at checkout", hi: "{count} · स्लॉट चेकआउट पर चुनें" },
  cartEmpty: { en: "Your cart is empty", hi: "आपका कार्ट खाली है" },
  cartEmptyHint: {
    en: "Add items yourself, or just tell the shopkeeper what you need.",
    hi: "खुद सामान डालिए, या बस दुकानदार को बताइए।",
  },
  browse: { en: "Browse", hi: "ब्राउज़ करें" },
  talkToBuy: { en: "Talk to buy", hi: "बोलकर खरीदें" },
  addMore: { en: "Add more items", hi: "और सामान डालें" },
  applyCoupon: { en: "Apply coupon", hi: "कूपन लगाइए" },
  couponApplied: { en: "{code} applied", hi: "{code} लगा" },
  couponSubIdle: { en: "Preview offers (demo)", hi: "ऑफ़र देखिए (डेमो)" },
  couponSubOn: { en: "Saves {x} · demo preview, tap to change", hi: "{x} की बचत · डेमो, बदलने के लिए दबाएँ" },
  tipTitle: { en: "Tip your delivery partner", hi: "डिलीवरी पार्टनर को टिप दें" },
  tipSub: { en: "Demo preview. Not added to your order.", hi: "डेमो। आपके ऑर्डर में नहीं जुड़ती।" },
  tipNone: { en: "None", hi: "नहीं" },
  billTitle: { en: "Bill details", hi: "बिल का ब्यौरा" },
  billItems: { en: "Item total", hi: "सामान का कुल" },
  billDelivery: { en: "Delivery fee", hi: "डिलीवरी शुल्क" },
  billFree: { en: "FREE", hi: "मुफ़्त" },
  billCoupon: { en: "Coupon {code} (demo)", hi: "कूपन {code} (डेमो)" },
  billTip: { en: "Tip (demo)", hi: "टिप (डेमो)" },
  toPay: { en: "To pay", hi: "कुल देय" },
  billNote: {
    en: "The order total comes from the store. Coupons and tips here are a demo preview and are not added to it.",
    hi: "ऑर्डर का कुल दाम दुकान से आता है। यहाँ के कूपन और टिप सिर्फ़ डेमो हैं, कुल में नहीं जुड़ते।",
  },
  deliveringTo: { en: "Delivering to {label}", hi: "{label} पर डिलीवरी" },
  checkOut: { en: "Check out", hi: "चेकआउट" },
  checkingOut: { en: "Asking the shopkeeper…", hi: "दुकानदार से पूछ रहे हैं…" },
  checkoutAsk: {
    en: "That is all, please check out my cart.",
    hi: "बस, मेरा कार्ट चेकआउट कर दीजिए।",
  },
  cancelOrder: { en: "Cancel order", hi: "ऑर्डर रद्द करें" },
  cancelAsk: { en: "Please cancel my order.", hi: "मेरा ऑर्डर कैंसल कर दीजिए।" },
  offersTitle: { en: "Offers and coupons", hi: "ऑफ़र और कूपन" },
  offersDemo: { en: "Demo offers: preview only.", hi: "डेमो ऑफ़र: सिर्फ़ दिखाने के लिए।" },
  couponFlat50: { en: "Flat ₹50 off", hi: "₹50 की छूट" },
  couponFlat50Note: { en: "On orders above ₹299", hi: "₹299 से ऊपर के ऑर्डर पर" },
  couponPct10: { en: "10% off, up to ₹60", hi: "10% छूट, ₹60 तक" },
  couponPct10Note: { en: "On orders above ₹199", hi: "₹199 से ऊपर के ऑर्डर पर" },
  couponLocked: { en: "Add {x} more to unlock", hi: "{x} और जोड़ें तो खुलेगा" },
  apply: { en: "Apply", hi: "लगाएँ" },
  remove: { en: "Remove", hi: "हटाएँ" },
  locked: { en: "Locked", hi: "बंद" },

  // payment
  payTitle: { en: "Payment", hi: "भुगतान" },
  payToPay: { en: "To pay {x}", hi: "देय {x}" },
  change: { en: "Change", hi: "बदलें" },
  payWith: { en: "Pay with", hi: "भुगतान का तरीका" },
  payUpi: { en: "UPI", hi: "UPI" },
  payUpiSub: { en: "Pay with any UPI app", hi: "किसी भी UPI ऐप से" },
  payCard: { en: "Credit or debit card", hi: "क्रेडिट या डेबिट कार्ड" },
  payCardSub: { en: "Visa, Mastercard and RuPay", hi: "Visa, Mastercard और RuPay" },
  payWallet: { en: "Talk to Buy Cash", hi: "टॉक टू बाय कैश" },
  payWalletSub: { en: "Wallet balance ₹120", hi: "वॉलेट में ₹120" },
  payCod: { en: "Pay on delivery", hi: "डिलीवरी पर भुगतान" },
  payCodSub: { en: "Cash or UPI to the delivery partner", hi: "डिलीवरी पार्टनर को नकद या UPI" },
  payNote: {
    en: "Demo: the methods above are for the look only. Your order is approved with your fingerprint, never by voice. No OTP or PIN is ever asked.",
    hi: "डेमो: ऊपर के तरीके सिर्फ़ दिखाने के लिए हैं। ऑर्डर की मंज़ूरी सिर्फ़ फ़िंगरप्रिंट से होगी, बोलकर नहीं। कोई OTP या PIN नहीं माँगा जाएगा।",
  },
  payTotal: { en: "Total", hi: "कुल" },
  payFingerprint: { en: "Pay {x} with fingerprint", hi: "फ़िंगरप्रिंट से {x} दें" },
  payWait: { en: "Please wait…", hi: "रुकिए…" },
  paySettingUp: { en: "Setting up fingerprint…", hi: "फ़िंगरप्रिंट जोड़ रहे हैं…" },
  payTestMode: { en: "Test mode", hi: "टेस्ट मोड" },
  payErrCancelled: {
    en: "Fingerprint not completed. Try again or go back.",
    hi: "फ़िंगरप्रिंट नहीं हुआ। फिर से कोशिश करें, या पीछे जाएँ।",
  },
  payErrFailed: {
    en: "Payment could not be approved. Please try again.",
    hi: "भुगतान अभी नहीं हो पाया। फिर से कोशिश करें।",
  },
  payNoRequest: {
    en: "Nothing to pay yet. Check out from your cart first.",
    hi: "अभी भुगतान के लिए कुछ नहीं है। पहले कार्ट से चेकआउट करें।",
  },
  slot: { en: "Delivery slot", hi: "डिलीवरी स्लॉट" },

  // track / placed
  trackTitle: { en: "Your order", hi: "आपका ऑर्डर" },
  trackTag0: { en: "Order placed", hi: "ऑर्डर हो गया" },
  trackTag1: { en: "Packing your order", hi: "पैकिंग हो रही है" },
  trackTag2: { en: "On the way", hi: "रास्ते में" },
  trackTag3: { en: "Delivered", hi: "पहुँच गया" },
  trackHead0: { en: "Thank you!", hi: "धन्यवाद!" },
  trackHead1: { en: "Getting it ready", hi: "तैयारी हो रही है" },
  trackHead2: { en: "Arriving shortly", hi: "जल्दी पहुँचेगा" },
  trackHead3: { en: "Enjoy your order", hi: "आनंद लीजिए" },
  trackSub: { en: "To {label} · {slot}", hi: "{label} · {slot}" },
  trackDemo: { en: "Demo tracking: progress is simulated.", hi: "डेमो ट्रैकिंग: प्रगति नकली है।" },
  orderId: { en: "Order {id}", hi: "ऑर्डर {id}" },
  riderAssigning: { en: "Assigning your delivery partner", hi: "डिलीवरी पार्टनर तय हो रहा है" },
  riderStore: { en: "Heading to the store", hi: "दुकान की ओर जा रहे हैं" },
  riderWay: { en: "On the way to you", hi: "आपके पास आ रहे हैं" },
  riderDone: { en: "Delivered", hi: "पहुँचा दिया" },
  mapLabel: { en: "Map showing the delivery route from the store to your address", hi: "दुकान से आपके पते तक का रास्ता" },
  orderSummary: { en: "Order summary", hi: "ऑर्डर का सार" },
  invoice: { en: "Invoice", hi: "बिल" },
  help: { en: "Help", hi: "मदद" },
  backHome: { en: "Back to home", hi: "होम पर वापस" },
  callPartner: { en: "Call delivery partner", hi: "डिलीवरी पार्टनर को फ़ोन" },

  // help sheet
  helpTitle: { en: "Need help?", hi: "मदद चाहिए?" },
  helpCall: { en: "Call delivery partner", hi: "डिलीवरी पार्टनर को फ़ोन करें" },
  helpCallNote: { en: "Demo: connecting you through a masked number.", hi: "डेमो: छुपे हुए नंबर से जोड़ रहे हैं।" },
  helpChat: { en: "Chat with support", hi: "सहायता से चैट करें" },
  helpChatNote: { en: "Demo: a support agent will join this chat shortly.", hi: "डेमो: सहायता एजेंट जल्द जुड़ेगा।" },
  helpInvoice: { en: "Download invoice", hi: "बिल डाउनलोड करें" },
  helpInvoiceNote: { en: "Demo: your invoice has been sent to your email.", hi: "डेमो: बिल आपके ईमेल पर भेज दिया गया है।" },
  helpReport: { en: "Report a problem", hi: "समस्या बताएँ" },
  helpReportNote: { en: "Demo: tell us what went wrong.", hi: "डेमो: बताइए क्या गड़बड़ हुई।" },

  // settings
  settingsTitle: { en: "Settings", hi: "सेटिंग" },
  languageTitle: { en: "Language / भाषा", hi: "भाषा / Language" },
  languageSub: { en: "The shopkeeper speaks and writes in this language.", hi: "दुकानदार इसी भाषा में बोलेगा और लिखेगा।" },
  languageNote: {
    en: "Changing language starts a new conversation and empties the cart.",
    hi: "भाषा बदलने पर नई बातचीत शुरू होगी और कार्ट खाली हो जाएगा।",
  },
  comingSoon: { en: "Coming soon", hi: "जल्द आ रहा है" },
  familyView: { en: "Family view", hi: "परिवार" },
  deliveryAddress: { en: "Delivery address", hi: "डिलीवरी का पता" },

  // family
  shareTitle: { en: "Share my cart live", hi: "मेरा कार्ट लाइव दिखाएँ" },
  shareSub: { en: "Family can see what you are adding while you talk. (Demo)", hi: "बोलते समय परिवार देख सकेगा आप क्या डाल रहे हैं। (डेमो)" },
  shareAria: { en: "Share cart with family", hi: "परिवार को कार्ट दिखाएँ" },
  familyWho: { en: "Who is in your family", hi: "आपके परिवार में कौन है" },
  roleOwner: { en: "Owner", hi: "मालिक" },
  roleCanOrder: { en: "Can order", hi: "ऑर्डर कर सकते हैं" },
  roleViewOnly: { en: "View only", hi: "सिर्फ़ देख सकते हैं" },
  familyNote: {
    en: "Members who can order can use TalkToBuy from their own phone, by voice, on your address. (Demo)",
    hi: "ऑर्डर कर सकने वाले सदस्य अपने फ़ोन से, बोलकर, आपके पते पर ऑर्डर कर सकेंगे। (डेमो)",
  },
  familySummary: { en: "{share} · {n} can order", hi: "{share} · {n} ऑर्डर कर सकते हैं" },
  sharingLive: { en: "Sharing live", hi: "लाइव दिखा रहे हैं" },
  notSharing: { en: "Not sharing", hi: "नहीं दिखा रहे" },
  you: { en: "You", hi: "आप" },
  alertsFor: { en: "Alerts for {name}", hi: "{name} के लिए सूचनाएँ" },
  alertsEvery: { en: "Updates every 3 seconds", hi: "हर 3 सेकंड में अपडेट" },
  alertsEmpty: { en: "No alerts yet", hi: "अभी कोई सूचना नहीं" },
  alertsOffline: { en: "Can't reach the server, retrying…", hi: "सर्वर से नहीं जुड़ पाए, फिर कोशिश कर रहे हैं…" },

  // address
  addressTitle: { en: "Delivery address", hi: "डिलीवरी का पता" },
  addressNote: {
    en: "The shopkeeper reads this address back to you before placing the order.",
    hi: "ऑर्डर देने से पहले दुकानदार यह पता आपको पढ़कर सुनाएगा।",
  },
  addressNew: { en: "Add a new address", hi: "नया पता जोड़ें" },
  addressSave: { en: "Save address", hi: "पता सहेजें" },
  fieldLabel: { en: "Name this address (optional)", hi: "इस पते का नाम (वैकल्पिक)" },
  fieldName: { en: "Name", hi: "नाम" },
  fieldLine1: { en: "House no. and street", hi: "मकान नंबर और गली" },
  fieldArea: { en: "Area", hi: "इलाका" },
  fieldCity: { en: "City", hi: "शहर" },
  fieldPincode: { en: "Pincode (6 digits)", hi: "पिनकोड (6 अंक)" },
  fieldPhone: { en: "Phone number (10 digits)", hi: "फ़ोन नंबर (10 अंक)" },
  errFill: { en: "Please fill in every field.", hi: "कृपया सभी जानकारी भरिए।" },
  errPincode: { en: "Pincode must be 6 digits.", hi: "पिनकोड 6 अंकों का होना चाहिए।" },
  errPhone: { en: "Phone number must be 10 digits.", hi: "फ़ोन नंबर 10 अंकों का होना चाहिए।" },
  errSave: { en: "Could not save the address. Try again.", hi: "पता सहेजा नहीं जा सका। फिर कोशिश करें।" },
  addressLoadError: { en: "Could not load your addresses.", hi: "आपके पते लोड नहीं हो पाए।" },

  // assistant host
  assistantTitle: { en: "TalkToBuy", hi: "TalkToBuy" },
  assistantAsking: { en: "Asking the shopkeeper…", hi: "दुकानदार से पूछ रहे हैं…" },
  assistantFailed: {
    en: "Could not reach the shopkeeper. Check your connection and try again.",
    hi: "दुकानदार से नहीं जुड़ पाए। कनेक्शन देखकर फिर कोशिश करें।",
  },
  addAsk: { en: "Please add {name} to my cart.", hi: "मेरे कार्ट में {name} डाल दीजिए।" },
  addOneAsk: { en: "Please add one more {name}.", hi: "एक और {name} डाल दीजिए।" },
  removeOneAsk: { en: "Please remove one {name} from my cart.", hi: "मेरे कार्ट से एक {name} हटा दीजिए।" },
  removeAllAsk: { en: "Please remove {name} from my cart.", hi: "मेरे कार्ट से {name} हटा दीजिए।" },
  endTalk: { en: "End and go back", hi: "खत्म करें और पीछे जाएँ" },
  settings: { en: "Settings", hi: "सेटिंग" },
} as const;

/** Exported for the translation-coverage test. */
export const STRINGS = DICT;

export type StringKey = keyof typeof DICT;

export function translate(lang: Lang, key: StringKey, vars?: Record<string, string | number>): string {
  const entry = DICT[key];
  const text: string = entry[lang] ?? entry.en;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (_m, name: string) => String(vars[name] ?? ""));
}

export type TFn = (key: StringKey, vars?: Record<string, string | number>) => string;

export const LangContext = createContext<Lang>("hi");

/** `const t = useT(); t("navHome")`: the label in the shopper's language. */
export function useT(): TFn {
  const lang = useContext(LangContext);
  return (key, vars) => translate(lang, key, vars);
}

export function useLang(): Lang {
  return useContext(LangContext);
}
