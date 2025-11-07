Below is a concise profile of ZETIC.ai, based on a crawl of its public site.

Summary
ZETIC.ai is a developer platform focused on on-device AI that enables organizations to build and ship AI apps without GPU servers, emphasizing lower cost, privacy, and real-time performance. Its core offering is ZETIC.MLange, an on‑device AI framework/SDK for iOS and Android that leverages mobile NPUs for efficient inference and supports a broad range of models (e.g., object detection, face analytics). The company positions its solution as “zero‑cost on‑device AI” to reduce reliance on cloud inference and server spend, while improving latency and data security (homepage meta/hero; blog).

Core product and capabilities
- ZETIC.MLange (on‑device AI SDK/framework):  
  - Runs AI models directly on mobile/edge devices using device NPUs; supports iOS and Android. SDK artifacts include Android AAR and iOS frameworks, plus a model-key generator (mlange_gen) to package models for on-device deployment (blogs: YOLOv8, Face Detection, Face Landmark, Face Emotion Recognition).  
  - Developer APIs (e.g., ZeticMLangeModel, ZeticMLangeFeatureYolov8/FaceDetection/FaceLandmark/FaceEmotionRecognition), sample repos, and step‑by‑step implementation guides are provided (blogs).  
  - Demonstrated model types: YOLOv8 object detection, Mediapipe Face Detection and Face Landmark, Face Emotion Recognition (EMO‑AffectNet) with example pipelines and code (blogs).
- Value propositions emphasized: zero/low server cost, privacy (data stays on device), low latency and offline operation, energy efficiency vs. cloud data centers (homepage meta; multiple blog explainers).
- Platform claims:  
  - “Now available for every model, every device” and “Make AI App without GPU Server” (homepage hero).  
  - Supports iOS/Android and “multiple NPUs” (homepage meta).  
  - Blog claims include support for “99% of mobile environments worldwide” and “on‑device AI implementation within 24 hours,” plus a ready‑to‑use AI module library (blog: The Rise of On‑Device AI: Challenges and Solutions / 온디바이스 AI, 혁신을 이끌다).

Target users and use cases
- Audience: Developers, startups, and enterprises building mobile/edge AI applications who want to cut inference costs, reduce latency, and improve data security (info across homepage/blog).
- Example applications and domains from tutorials: real‑time object detection, face detection/landmark/emotion recognition; broader mentions include CCTV/IoT, wearables, smart home, industrial sensors (YOLOv8 and face-analytics blog posts).

Mission/positioning
- Tagline/position: “Build Zero‑cost On‑device AI” and “Make AI App without GPU Server” (homepage).  
- Vision themes in blogs: “AI for all” via on‑device AI that reduces costs, environmental impact, and network dependency while enhancing privacy.

Notable details and content
- Documentation and code: implementation guides for Android (Java/Kotlin) and iOS (Swift), with code snippets, pipelines, and links to demo assets (blogs).  
- Tooling: mlange_gen utility to generate a “MLange Model Key” from ONNX/Torch/TFLite artifacts before deploying with the SDK (blogs).  
- Knowledge hub: A blog covering on‑device AI fundamentals, industry challenges, climate/energy implications of AI, business trends, and how-tos with dated posts (2024–2025).  
- Contact: contact@zetic.ai (blog/CTA).  
- Organization: Posts indicate Korean and English content (bilingual site); one post references a visit at Maru 180 (a startup hub in Seoul), suggesting a Korea presence (blog: 미래의 엔지니어들…).

Distinctive aspects
- End‑to‑end on‑device SDK with target‑device NPU optimization, developer‑friendly APIs, and quick packaging (mlange_gen).  
- Aggressive operational claims in blogs: support for “99% of mobile environments” and the ability to implement on‑device AI “within 24 hours,” plus a “ready‑to‑use AI module library” (blog).  
- Practical, code‑level tutorials for deploying common models (YOLOv8, Mediapipe‑based) on devices.

Selected sources (internal pages)
- Homepage/meta (on‑device AI positioning and platform compatibility): https://zetic.ai/ (Framer page); meta shows iOS/Android/NPU support.  
- Blog tutorials and explainers:  
  - YOLOv8 on‑device with ZETIC.MLange: /blog/implementing-yolov8-on-device-ai-with-zetic-mlange  
  - Face Detection: /blog/implementing-face-detection-on-device-ai-with-zetic-mlange  
  - Face Landmark: /blog/implementing-face-landmark-on-device-ai-with-zetic-mlange  
  - Face Emotion Recognition: /blog/implementing-face-emotion-recognition-on-device-ai-with-zetic-mlange  
  - On‑device AI challenges/solutions (claims on 99% mobile support, 24‑hour implementation): /blog/the-rise-of-on-device-ai-challenges-and-solutions (and Korean counterpart)  
  - On‑device AI benefits and industry challenges: /blog/benefits-of-on-device-ai-and-addressing-ai-industry-challenges

Most relevant data points to retain
- Company: ZETIC.ai (developer platform for on‑device AI).  
- Core product: ZETIC.MLange (on‑device AI framework/SDK for iOS/Android NPUs).  
- Key features: on‑device inference; mlange_gen model key generator; Android AAR and iOS frameworks; developer feature modules (Yolov8, Face Detection, Face Landmark, Face Emotion).  
- Value propositions: zero/low server cost; privacy (data stays on device); low latency; offline operation; energy efficiency.  
- Target users: developers, startups, and enterprises building AI apps for mobile/edge (object detection, face analytics, IoT/CCTV/wearables, etc.).  
- Claimed platform reach and speed: “supports 99% of mobile environments”; “on‑device AI implementation within 24 hours” (from blog).  
- Docs/examples: code and step‑by‑step guides for Android/iOS; pipelines combining detection + downstream tasks; sample repos linked in blogs.  
- Contact: contact@zetic.ai.  
- Content languages: English and Korean; blog dates (2024–2025).  
- Positioning tagline: “Build Zero‑cost On‑device AI” / “Make AI App without GPU Server.”
