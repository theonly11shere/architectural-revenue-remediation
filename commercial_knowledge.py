"""Expanded commercial evidence vocabulary for Trilloka V7.3.2.

This module does NOT change Trilloka's decision logic. It expands the evidence vocabulary
available to the existing Business Type + Journey + Context + Verified Evidence model.
Weights remain bounded hints; they never create checkpoint failures by themselves.
"""

BUSINESS_PHRASE_EXPANSIONS = {
    "restaurant": (
        ("cafe",5),("café",5),("coffee shop",6),("bistro",6),("eatery",6),("diner",6),("food menu",5),
        ("dine in",6),("dine-in",6),("take out",5),("take-out",5),("pickup order",5),("order food",6),
        ("pho",4),("banh mi",4),("noodle soup",3),("cuisine",3),("appetizers",3),("vermicelli",3),
        ("breakfast",2),("lunch",2),("dinner",2),("opening hours",1.5),("business hours",1.5),
        ("food delivery",4),("table reservation",7),("our restaurant",7),("chef",3),("fresh ingredients",2),
    ),
    "ecommerce": (
        ("online shop",7),("online store",7),("shop all",5),("product catalog",5),("product catalogue",5),
        ("add to bag",7),("your cart",6),("basket",4),("secure checkout",7),("free shipping",4),
        ("delivery",2),("in stock",4),("out of stock",4),("sku",3),("quantity",2),("sale price",3),
        ("buy online",7),("place order",6),("payment methods",4),("shop pay",5),("afterpay",4),("klarna",4),
    ),
    "local_service": (
        ("serving the area",4),("areas we serve",6),("service areas",6),("same day service",5),("emergency service",5),
        ("book service",6),("schedule service",6),("request service",6),("get estimate",6),("get an estimate",6),
        ("licensed and insured",5),("residential services",4),("commercial services",3),("technician",3),
        ("electrician",5),("plumber",5),("roofer",5),("landscaping",5),("pest control",5),("hvac",5),
        ("carpet cleaning",5),("house cleaning",5),("junk removal",5),("movers",5),("moving services",5),
    ),
    "professional_service": (
        ("consultancy",6),("consultant",5),("advisors",5),("advisers",5),("our expertise",3),("our professionals",4),
        ("book consultation",6),("initial consultation",6),("client services",4),("strategy consulting",6),
        ("tax services",5),("bookkeeping",5),("business advisory",6),("management consulting",6),
    ),
    "healthcare": (
        ("health centre",6),("health center",6),("medical centre",7),("medical center",7),
        ("family doctor",6),("walk-in clinic",7),("walk in clinic",7),("dental",5),("physio",5),
        ("registered massage",6),("rmt",4),("therapy",3),("treatment",2),("patients",4),("patient care",5),
        ("book your appointment",7),("health services",5),("healthcare",6),
    ),
    "medspa": (
        ("medical aesthetics",8),("aesthetic medicine",8),("injectables",6),("dermal filler",6),("fillers",5),
        ("skin rejuvenation",5),("laser hair removal",6),("microneedling",5),("facial treatment",4),
    ),
    "legal": (
        ("law office",8),("legal counsel",7),("barrister",7),("solicitor",7),("litigation",5),("legal advice",6),
        ("practice areas",5),("family law",6),("criminal law",6),("immigration law",6),("personal injury",5),
    ),
    "financial_services": (
        ("wealth advisor",8),("financial adviser",8),("portfolio management",7),("asset management",7),
        ("mortgage broker",7),("insurance advisor",7),("retirement planning",6),("investment management",7),
        ("financial solutions",4),("credit union",6),("lending",5),("loan application",5),
    ),
    "real_estate": (
        ("real estate agent",8),("property search",7),("list your home",7),("sell your home",7),("buy a home",7),
        ("mls",6),("open house",5),("property management",6),("commercial property",5),("condos for sale",6),
    ),
    "hospitality_event": (
        ("accommodation",5),("rooms and suites",7),("book your stay",8),("check availability",7),("guest rooms",6),
        ("conference venue",7),("event space",7),("banquet hall",7),("guided tour",6),("book a tour",7),
        ("vacation",3),("resort",7),("bed and breakfast",7),("bnb",4),
    ),
    "saas": (
        ("cloud software",7),("web app",5),("api",3),("developer platform",6),("automation platform",6),
        ("book demo",7),("request demo",8),("pricing plans",5),("per month",3),("per user",4),
        ("sign up free",6),("get started free",6),("dashboard",2),("workflow",2),("integration",3),
    ),
    "b2b": (
        ("business to business",8),("for businesses",4),("for enterprises",6),("distributor",5),("supplier",5),
        ("supply chain",5),("freight",5),("warehousing",5),("commercial solutions",5),("request rfq",7),
        ("request for quote",7),("industries served",5),("dealers",3),("partners",2),
    ),
    "agency": (
        ("web agency",8),("branding agency",8),("seo agency",8),("pr agency",8),("creative studio",6),
        ("our work",3),("client work",4),("case studies",3),("brand strategy",5),("web design",4),
    ),
    "membership_creator": (
        ("members only",6),("member benefits",6),("join the community",6),("paid newsletter",6),
        ("subscriber",4),("subscribers",4),("exclusive content",5),("monthly membership",7),
    ),
    "education": (
        ("learning",3),("students",4),("student",3),("enrolment",6),("enrollment",6),("curriculum",5),
        ("certificate program",6),("online course",5),("classes",3),("instructor",4),("faculty",5),
        ("tuition fees",6),("student services",5),
    ),
    "nonprofit": (
        ("not-for-profit",9),("not for profit",9),("donor",5),("donors",5),("fundraising",6),("our mission",4),
        ("community organization",5),("community organisation",5),("make a gift",7),("ways to give",7),
    ),
    "automotive": (
        ("auto service",7),("automotive service",7),("mechanic",6),("oil change",5),("tire service",5),
        ("vehicle inventory",6),("new vehicles",5),("pre-owned",5),("book a test drive",7),("test drive",6),
        ("parts department",5),("service department",5),
    ),
}

JOURNEY_PHRASE_EXPANSIONS = {
    "lead_quote": (("get an estimate",7),("get estimate",7),("request pricing",6),("tell us about your project",6),("start your project",5),("get a proposal",7),("rfq",6),("contact our team",3)),
    "appointment_consultation": (("book online",6),("schedule online",6),("make an appointment",7),("reserve appointment",6),("initial consultation",6),("free consultation",6),("schedule a call",5),("book a call",5)),
    "reservation_event": (("dine in",4),("dine-in",4),("table booking",7),("reserve a table",8),("make a reservation",8),("order for pickup",5),("pickup",2),("get directions",2),("opening hours",2),("business hours",2),("book your stay",8),("check availability",7)),
    "direct_purchase": (("add to bag",8),("add to basket",8),("place order",7),("buy online",7),("order now",7),("secure checkout",7),("payment",2),("in stock",2),("quantity",1.5)),
    "demo_sales": (("schedule demo",8),("talk to sales",8),("speak to sales",8),("sales team",5),("get started free",6),("sign up free",6),("contact our sales",8)),
    "membership_subscription": (("sign up",4),("become a subscriber",7),("member benefits",6),("monthly plan",5),("annual plan",5),("join community",6)),
    "donation_support": (("ways to give",7),("make a gift",8),("become a donor",7),("fundraise",5),("sponsor",4)),
    "application_enrollment": (("enrol today",7),("enroll today",7),("request information",5),("student application",7),("registration form",6),("admission",5)),
}

GENERAL_DISCOVERY_TERMS = (
    "menu","dine","restaurant","cafe","location","locations","hours","directions","order","shop","product","products",
    "pricing","price","book","booking","reserve","reservation","appointment","consultation","quote","estimate","services",
    "service","contact","about","team","reviews","testimonials","case-studies","portfolio","faq","delivery","shipping",
    "returns","refund","apply","admissions","donate","membership","subscribe","demo","trial","solutions","events"
)

GENERAL_PAGE_GUESSES = [
    "/contact/","/services/","/about/","/menu/","/dine-in_menu/","/location/","/locations/","/hours/",
    "/order/","/order-online/","/shop/","/products/","/pricing/","/book/","/booking/","/reservations/",
    "/appointments/","/consultation/","/request-a-quote/","/reviews/","/testimonials/","/faq/"
]

LOCAL_TERM_EXPANSIONS = (
    "address","business hours","opening hours","open today","get directions","parking","pickup","pick up","dine in",
    "serving richmond","serving vancouver","serving burnaby","serving surrey","serving coquitlam","serving our community"
)

HOSPITALITY_TERM_EXPANSIONS = (
    "cafe","café","dine in","dine-in","menu","food","cuisine","opening hours","business hours","book a table",
    "reserve a table","order online","pickup","takeout","take out"
)

# V7.3.3 broad-spectrum expansion. These are recognition signals only: they do not
# create findings, alter checkpoint applicability, or bypass UNKNOWN/N/A safeguards.
BROAD_BUSINESS_PHRASE_EXPANSIONS = {
    "ecommerce": (("shop collection",5),("collections",2),("product details",4),("product reviews",4),("size guide",4),("shipping policy",5),("return policy",5),("wishlist",3),("discount code",3),("checkout",7),("free returns",4),("preorder",4),("pre-order",4),("subscription box",3),("gift card",3),("compare products",3),("variant",2),("color options",2),("size options",2)),
    "marketplace": (("become a seller",8),("seller dashboard",8),("buyer protection",7),("vendor portal",7),("list an item",7),("service providers",4),("find a provider",5),("book a provider",5),("commission",3),("seller fees",5),("buyer fees",5),("verified sellers",5),("provider profiles",5),("browse listings",5),("post a job",5),("submit a listing",6)),
    "local_service": (("free quote",6),("instant quote",6),("request a quote",7),("24/7 service",5),("same-day",4),("locally owned",5),("service call",5),("on-site service",5),("homeowners",3),("repair service",5),("installation service",5),("maintenance service",5),("before and after",3),("project gallery",3),("warranty",2),("financing available",3),("service booking",6),("licensed contractor",6)),
    "professional_service": (("advisory firm",7),("consulting firm",7),("our approach",3),("our process",3),("engagement",2),("client success",4),("schedule consultation",6),("professional advice",5),("audit services",5),("accounting firm",7),("cpa firm",7),("tax advisory",6),("business consulting",6),("strategy services",5),("expertise",2),("industries we serve",3)),
    "healthcare": (("health care",5),("medical practice",7),("patient portal",7),("new patients",6),("book appointment",7),("schedule appointment",7),("treatments",3),("conditions we treat",5),("insurance accepted",5),("direct billing",4),("telehealth",5),("virtual care",5),("prescription",3),("registered therapist",5),("occupational therapy",6),("counselling",5),("counseling",5)),
    "medspa": (("botox",6),("neuromodulator",6),("cosmetic injections",7),("skin clinic",5),("aesthetic clinic",8),("body contouring",6),("laser treatment",5),("chemical peel",5),("hydrafacial",5),("skin consultation",6),("before & after",4),("before and after",4),("cosmetic treatment",6),("anti-aging",4),("anti ageing",4)),
    "legal": (("attorneys",7),("lawyers",7),("legal representation",7),("legal consultation",6),("case evaluation",6),("free case review",7),("practice area",5),("corporate law",6),("business law",6),("estate law",6),("real estate law",6),("employment law",6),("civil litigation",6),("defence lawyer",6),("defense attorney",6),("legal team",5)),
    "financial_services": (("financial planning",8),("investment planning",7),("insurance brokerage",7),("mortgage advisor",7),("mortgage agent",7),("financial consultant",6),("wealth planning",7),("estate planning",5),("tax planning",5),("portfolio",3),("investments",3),("insurance quote",5),("apply for a loan",6),("credit application",6),("rates",2),("assets under management",5)),
    "real_estate": (("realtor",8),("realty",7),("homes for sale",8),("properties for sale",8),("property listings",8),("featured listings",7),("home valuation",7),("what is my home worth",7),("book a viewing",6),("schedule a showing",7),("listing agent",6),("buyer agent",6),("rentals",3),("commercial real estate",7),("property manager",6),("neighbourhoods",3),("neighborhoods",3)),
    "restaurant": (("food & drink",4),("food and drink",4),("our menu",6),("view menu",6),("order online",6),("takeaway",5),("takeout",5),("take-out",5),("reservations",6),("table booking",7),("happy hour",4),("brunch",4),("dessert",3),("cocktails",3),("wine list",4),("daily special",3),("chef's menu",5),("catering menu",4)),
    "hospitality_event": (("hotel rooms",7),("room booking",8),("accommodations",6),("check-in",5),("check out date",5),("nightly rate",5),("guest stay",5),("amenities",3),("wedding packages",7),("event packages",7),("meeting rooms",6),("conference rooms",6),("venue hire",7),("event booking",7),("tour booking",7),("tickets",3),("attractions",3),("itinerary",3)),
    "saas": (("software",4),("platform",3),("product tour",6),("free trial",7),("start trial",7),("request a demo",8),("contact sales",8),("enterprise plan",6),("pricing",3),("features",2),("integrations",4),("api docs",5),("developer docs",5),("security",2),("sso",3),("workflow automation",6),("user seats",4),("per seat",4),("monthly subscription",4),("annual subscription",4)),
    "b2b": (("industrial solutions",6),("commercial clients",5),("enterprise clients",6),("request a proposal",7),("request a quotation",7),("rfp",5),("rfq",6),("manufacturing",6),("manufacturer",6),("distributor",6),("wholesale",6),("logistics",5),("fleet",4),("procurement",6),("supply chain",6),("technical specifications",4),("industries",2),("case studies",3),("partner network",4)),
    "agency": (("marketing services",6),("creative agency",9),("digital marketing",6),("brand agency",8),("performance marketing",6),("media buying",6),("public relations",6),("content agency",7),("design studio",7),("portfolio",3),("selected work",4),("our clients",3),("client results",5),("campaigns",3),("book a discovery call",7),("start a project",6)),
    "membership_creator": (("membership plans",7),("join membership",7),("premium membership",7),("community access",6),("member portal",7),("subscriber-only",6),("subscriber only",6),("exclusive access",5),("creator community",6),("paid community",7),("newsletter subscription",5),("supporter tier",6),("membership tier",6),("join us",3)),
    "education": (("school",6),("training",4),("course catalog",6),("course catalogue",6),("programs",3),("admissions",7),("apply now",6),("student portal",6),("learning outcomes",5),("degree",5),("diploma",5),("certificate",4),("workshop",3),("bootcamp",5),("academy",6),("university",9),("college",9),("tuition",6),("scholarship",5),("register for class",6)),
    "nonprofit": (("nonprofit",9),("non-profit",9),("charitable organization",8),("registered charity",9),("donate now",8),("donation",6),("volunteer",5),("program impact",6),("annual report",4),("our impact",5),("support our mission",7),("fundraiser",6),("sponsorship",4),("community programs",5),("tax receipt",6),("giving",5),("foundation",5)),
    "automotive": (("auto repair",8),("car repair",8),("vehicle repair",7),("auto dealer",8),("car dealer",8),("vehicle sales",7),("inventory",4),("book service",7),("service appointment",7),("parts & service",6),("parts and service",6),("tire change",5),("brake service",5),("collision repair",6),("body shop",6),("trade-in",6),("trade in",5),("vehicle financing",6),("test drive",7),("used vehicles",6)),
}

BROAD_JOURNEY_PHRASE_EXPANSIONS = {
    "lead_quote": (("free quote",8),("instant quote",8),("request quote",8),("request a proposal",8),("get pricing",6),("project inquiry",7),("project enquiry",7),("contact for pricing",6),("request consultation",5),("request information",4),("talk to an expert",5),("speak with an expert",5)),
    "appointment_consultation": (("book appointment",8),("schedule appointment",8),("book consultation",8),("schedule consultation",8),("book a visit",7),("schedule a visit",7),("book assessment",7),("schedule assessment",7),("book treatment",7),("patient booking",7),("book discovery call",6)),
    "reservation_event": (("reservations",7),("book a table",8),("table reservation",8),("book room",8),("reserve room",8),("book tickets",7),("reserve tickets",7),("book event",7),("venue booking",7),("check room availability",7),("reserve your stay",8),("book tour",7)),
    "direct_purchase": (("checkout",8),("buy",5),("purchase",5),("add to cart",9),("add to basket",9),("add to bag",9),("shop now",7),("complete order",8),("proceed to checkout",9),("pre-order",6),("preorder",6),("subscribe & save",5)),
    "demo_sales": (("request demo",9),("book demo",9),("get a demo",9),("contact sales",9),("talk to sales",9),("start free trial",8),("try for free",8),("start for free",7),("enterprise demo",9),("sales consultation",6),("product tour",5)),
    "membership_subscription": (("subscribe now",8),("join now",8),("become a member",9),("choose membership",8),("membership plan",7),("subscribe",6),("upgrade plan",6),("start membership",8),("join the community",7),("supporter membership",7)),
    "donation_support": (("donate",8),("donate now",9),("give now",9),("make a gift",9),("monthly giving",8),("become a donor",8),("support our mission",7),("fundraise",6),("sponsor",5),("volunteer",3)),
    "application_enrollment": (("apply",7),("apply now",9),("start application",9),("submit application",9),("enroll",8),("enrol",8),("register",7),("admissions application",8),("course registration",7),("program application",8),("request admissions info",5)),
}

# Merge broad expansion into the first expansion so architecture_model keeps exactly the
# same merge/inference mechanism and scoring behavior.
for _bt, _items in BROAD_BUSINESS_PHRASE_EXPANSIONS.items():
    BUSINESS_PHRASE_EXPANSIONS[_bt] = tuple(BUSINESS_PHRASE_EXPANSIONS.get(_bt, ())) + tuple(_items)
for _j, _items in BROAD_JOURNEY_PHRASE_EXPANSIONS.items():
    JOURNEY_PHRASE_EXPANSIONS[_j] = tuple(JOURNEY_PHRASE_EXPANSIONS.get(_j, ())) + tuple(_items)
