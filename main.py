import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from database import db, create_document, get_documents
from schemas import ChatSession, ChatMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI Agri Chatbot Backend Running"}

# Simple multilingual prompt templates (no external LLMs used)
PROMPTS: Dict[str, str] = {
    "en": "You are an agriculture assistant. Answer clearly and practically.",
    "hi": "आप एक कृषि सहायक हैं। स्पष्ट और व्यावहारिक उत्तर दें।",
    "ta": "நீங்கள் ஒரு வேளாண் உதவியாளர். தெளிவாகவும் நடைமுறையாகவும் பதிலளிக்கவும்.",
    "te": "మీరు వ్యవసాయ సహాయకులు. స్పష్టంగా మరియు ఆచరణాత్మకంగా సమాధానం ఇవ్వండి.",
    "bn": "আপনি একজন কৃষি সহকারী। পরিষ্কার এবং ব্যবহারিকভাবে উত্তর দিন।",
    "mr": "तुम्ही कृषी सहाय्यक आहात. स्पष्ट आणि व्यावहारिक उत्तर द्या.",
    "kn": "ನೀವು ಕೃಷಿ ಸಹಾಯಕರು. ಸ್ಪಷ್ಟವಾಗಿ ಮತ್ತು ಪ್ರಾಯೋಗಿಕವಾಗಿ ಉತ್ತರಿಸಿ.",
    "ml": "നിങ്ങൾ ഒരു കൃഷി സഹായിയാണ്. വ്യക്തമായും പ്രായോഗികമായും മറുപടി നൽകുക.",
    "pa": "ਤੁਸੀਂ ਖੇਤੀਬਾੜੀ ਸਹਾਇਕ ਹੋ। ਸਪੱਸ਼ਟ ਅਤੇ ਵਿਹਾਰਕ ਜਵਾਬ ਦਿਓ।",
    "gu": "તમે કૃષિ સહાયક છો. સ્પષ્ટ અને વ્યવહારુ જવાબ આપો.",
}

SUPPORTED_LANG = set(PROMPTS.keys())

class AskPayload(BaseModel):
    session_id: str
    language: str
    question: str

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:100]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:100]}"
    return response

@app.get("/languages")
def get_languages():
    return {"languages": sorted(list(SUPPORTED_LANG))}

@app.post("/chat/start")
def start_chat(payload: ChatSession):
    if payload.language not in SUPPORTED_LANG:
        raise HTTPException(status_code=400, detail="Unsupported language code")
    session_id = create_document("chatsession", payload)
    return {"session_id": session_id}

@app.get("/chat/{session_id}")
def get_chat_history(session_id: str):
    msgs = get_documents("chatmessage", {"session_id": session_id}, limit=100)
    # Convert ObjectId to string if needed
    for m in msgs:
        if "_id" in m:
            m["_id"] = str(m["_id"])
        if "created_at" in m:
            m["created_at"] = str(m["created_at"])
    return {"messages": msgs}

@app.post("/chat/ask")
def ask_question(payload: AskPayload):
    if payload.language not in SUPPORTED_LANG:
        raise HTTPException(status_code=400, detail="Unsupported language code")

    # Save user question
    create_document("chatmessage", ChatMessage(
        session_id=payload.session_id,
        role="user",
        content=payload.question,
        language=payload.language,
    ))

    # Generate a lightweight rule-based response (no external API)
    answer = generate_agri_answer(payload.question, payload.language)

    # Save assistant answer
    create_document("chatmessage", ChatMessage(
        session_id=payload.session_id,
        role="assistant",
        content=answer,
        language=payload.language,
    ))

    return {"answer": answer}


def generate_agri_answer(question: str, lang: str) -> str:
    q = question.lower()

    # Very lightweight intent detection
    if any(k in q for k in ["soil", "fertilizer", "fertiliser", "nutrient", "manure", "compost", "मिट्टी", "खाद", "மண்", "உரம்"]):
        base = {
            "en": "Soil health: Test soil pH and organic carbon yearly. Use compost and balanced N-P-K based on test.",
            "hi": "मृदा स्वास्थ्य: हर साल pH और कार्बन की जाँच करें। परीक्षण के आधार पर संतुलित N-P-K और कंपोस्ट दें।",
            "ta": "மண் ஆரோக்கியம்: ஆண்டுதோறும் pH மற்றும் கார்பன் சோதிக்கவும். சோதனை அடிப்படையில் N-P-K மற்றும் சோழம் சேர்க்கவும்.",
            "te": "నేల ఆరోగ్యం: ప్రతి సంవత్సరం pH మరియు కార్బన్ పరీక్షించండి. పరీక్ష ఆధారంగా సమతుల్య N-P-K మరియు కంపోస్ట్ వాడండి.",
            "bn": "মাটির স্বাস্থ্য: বছরে একবার pH ও কার্বন পরীক্ষা করুন। পরীক্ষার ভিত্তিতে সুষম N-P-K ও কম্পোস্ট দিন।",
            "mr": "मृदा आरोग्य: दरवर्षी pH आणि कार्बन तपासा. तपासणीवर आधारित संतुलित N-P-K आणि कंपोस्ट वापरा.",
            "kn": "ಮಣ್ಣಿನ ಆರೋಗ್ಯ: ವರ್ಷಕ್ಕೆ ಒಮ್ಮೆ pH ಮತ್ತು ಕಾರ್ಬನ್ ಪರೀಕ್ಷೆ ಮಾಡಿ. ಪರೀಕ್ಷೆಯ ಆಧಾರದ ಮೇಲೆ ಸಮತೋಲಿತ N-P-K ಮತ್ತು ಕೊಂಪೋಸ್ಟ್ ಬಳಸಿ.",
            "ml": "മണ്ണിന്റെ ആരോഗ്യം: വർഷത്തിൽ ഒരിക്കൽ pH, കാർബൺ പരിശോധിക്കുക. പരിശോധനയെ അടിസ്ഥാനപ്പെടുത്തി N-P-K, കമ്പോസ്റ്റ് നൽകുക.",
            "pa": "ਮਿੱਟੀ ਸਿਹਤ: ਸਾਲਾਨਾ pH ਤੇ ਕਾਰਬਨ ਦੀ ਜਾਂਚ ਕਰੋ। ਟੈਸਟ ਦੇ ਆਧਾਰ 'ਤੇ ਸੰਤੁਲਿਤ N-P-K ਤੇ ਕੰਪੋਸਟ ਦਿਓ।",
            "gu": "માટીની તંદુરસ્તી: દર વર્ષે pH અને કાર્બન તપાસો. પરીક્ષણના આધારે સંતુલિત N-P-K અને કમ્પોસ્ટ આપો.",
        }
        return base.get(lang, base["en"])  # default English

    if any(k in q for k in ["pest", "insect", "disease", "aphid", "fungus", "कीट", "रोग", "பூச்சி", "நோய்"]):
        base = {
            "en": "Pest management: Start with field scouting and traps. Prefer IPM: resistant varieties, crop rotation, botanicals.",
            "hi": "कीट प्रबंधन: फसल निरीक्षण और ट्रैप से शुरू करें। IPM अपनाएँ: रोग-रोधी किस्में, फसल चक्र, वनस्पति कीटनाशक।",
            "ta": "பூச்சி மேலாண்மை: வயல் கண்காணிப்பு, கண்ணிகள் மூலம் தொடங்கவும். IPM: நோய் எதிர்ப்பு வகைகள், பயிர் சுழற்சி, மூலிகை பூச்சிக்கொல்லிகள்.",
            "te": "పురుగు నిర్వహణ: క్షేత్ర పరిశీలన, ట్రాప్స్ తో ప్రారంభించండి. IPM: నిరోధక రకాలు, పంట మార్పిడి, బోటానికల్స్.",
            "bn": "পোকার দমন: মাঠ পর্যবেক্ষণ ও ফাঁদ দিয়ে শুরু করুন। IPM: রোগ-প্রতিরোধী জাত, শস্য পর্যায়ক্রম, উদ্ভিজ কীটনাশক।",
            "mr": "कीड व्यवस्थापन: शेत तपासणी, सापळ्यांपासून सुरुवात करा. IPM: प्रतिरोधक वाण, पीक फेरपालट, वनस्पतीजन्य कीटकनाशके.",
            "kn": "ಕೀಟ ನಿರ್ವಹಣೆ: ಕ್ಷೇತ್ರ ಪರಿಶೀಲನೆ, ಬೋನುಗಳಿಂದ ಆರಂಭಿಸಿ. IPM: ಪ್ರತಿರೋಧಕ ಜಾತಿಗಳು, ಬೆಳೆ ಬದಲಾವಣೆ, ಸಸ್ಯನಾಶಕಗಳು.",
            "ml": "കീടനാശനം: വയൽ നിരീക്ഷണവും കുടകളുമായി തുടങ്ങുക. IPM: രോഗപ്രതിരോധ ഇനങ്ങൾ, വിളപരിവർത്തനം, സസ്യാധിഷ്ഠിത കീടനാശിനികൾ.",
            "pa": "ਕੀਟ ਪ੍ਰਬੰਧਨ: ਖੇਤ ਦੀ ਜਾਂਚ ਤੇ ਫੰਧਿਆਂ ਨਾਲ ਸ਼ੁਰੂ ਕਰੋ। IPM: ਰੋਗ-ਰੋਧੀ ਕਿਸਮਾਂ, ਫਸਲ ਚੱਕਰ, ਬੋਟੈਨਿਕਲ ਕੀਟਨਾਸ਼ਕ।",
            "gu": "કીડ સંચાલન: ખેતર નિરીક્ષણ અને ટ્રેપથી શરૂઆત કરો. IPM: રોગપ્રતિરોધક જાતો, પાક ફરતી, બોટેનિકલ્સ.",
        }
        return base.get(lang, base["en"])  # default English

    # Default helpful reply
    base = {
        "en": "I can help with crop choice, soil, irrigation, pest control and local best practices. Please share location, crop and issue.",
        "hi": "मैं फसल चयन, मिट्टी, सिंचाई, कीट नियंत्रण और स्थानीय सर्वोत्तम उपायों में मदद कर सकता हूँ। कृपया स्थान, फसल और समस्या बताएं।",
        "ta": "பயிர் தேர்வு, மண், பாசனம், பூச்சி கட்டுப்பாடு மற்றும் உள்ளூர் சிறந்த நடைமுறைகளில் உதவலாம். இடம், பயிர், சிக்கலை பகிரவும்.",
        "te": "పంట ఎంపిక, నేల, సాగు, పురుగు నియంత్రణలో సహాయం చేస్తాను. దయచేసి ప్రదేశం, పంట, సమస్య చెప్పండి.",
        "bn": "ফসল নির্বাচন, মাটি, সেচ, পোকা দমন ইত্যাদিতে আমি সাহায্য করতে পারি। অনুগ্রহ করে স্থান, ফসল ও সমস্যা বলুন।",
        "mr": "पीक निवड, माती, सिंचन, किड नियंत्रण याबाबत मी मदत करू शकतो. कृपया ठिकाण, पीक आणि समस्या सांगा.",
        "kn": "ಬೆಳೆ ಆಯ್ಕೆ, ಮಣ್ಣು, ನೀರಾವರಿ, ಕೀಟ ನಿಯಂತ್ರಣದಲ್ಲಿ ನಾನು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ. ದಯವಿಟ್ಟು ಸ್ಥಳ, ಬೆಳೆ ಮತ್ತು ಸಮಸ್ಯೆ ಹಂಚಿಕೊಳ್ಳಿ.",
        "ml": "വിള തിരഞ്ഞെടുപ്പ്, മണ്ണ്, ജലസേചനം, കീടനിയന്ത്രണം എന്നിവയിൽ ഞാൻ സഹായിക്കും. സ്ഥലം, വിള, പ്രശ്നം പറയുക.",
        "pa": "ਫਸਲ ਚੋਣ, ਮਿੱਟੀ, ਸਿੰਚਾਈ, ਕੀਟ ਨਿਯੰਤਰਣ ਵਿੱਚ ਮੈਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ। ਕਿਰਪਾ ਕਰਕੇ ਥਾਂ, ਫਸਲ ਅਤੇ ਮੁੱਦਾ ਦੱਸੋ।",
        "gu": "હું પાક પસંદગી, માટી, સિંચાઈ, કીડ નિયંત્રણમાં મદદ કરી શકું છું. કૃપા કરવા સ્થળ, પાક અને સમસ્યા જણાવો.",
    }
    return base.get(lang, base["en"])  # default English


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
