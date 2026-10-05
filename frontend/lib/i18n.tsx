"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

/* ------------------------------------------------------------------ */
/*  Dictionary — the single source of truth for every visible string   */
/* ------------------------------------------------------------------ */

export type Lang = "ar" | "en";

const ar = {
  // Landing — hero
  hero_title: "اكشف الصور المزيفة بثقة",
  hero_sub:
    "يفحص DeepGuard كل صورة بأربعة كواشف مستقلة، ويمنحك حكمًا واضحًا مدعومًا بالدليل، وكل ذلك على جهازك دون رفع أي ملف.",
  cta_start: "ابدأ الفحص الآن",
  cta_how: "كيف يعمل؟",
  nav_open: "افتح المنصة",
  nav_features: "المميزات",
  nav_signals: "كيف يعمل",
  nav_how: "خطوات الفحص",
  nav_sim: "جرّب الحكم",
  nav_faq: "الأسئلة الشائعة",
  trust_local: "تعمل محليًا",
  trust_noupload: "لا رفع للصور",
  trust_evidence: "حكم مدعوم بالدليل",

  // Stats strip — 4 equal cards
  stat1_v: "4,803",
  stat1_l: "نموذج توليد مدرَّب عليه الكاشف",
  stat2_v: "4",
  stat2_l: "كواشف مستقلة تعمل بالتوازي",
  stat3_v: "0",
  stat3_l: "صورة تغادر جهازك",
  stat4_v: "100%",
  stat4_l: "فحص محلي بالكامل",

  // Detectors — 2×2 cards
  sec1_title: "كيف يكتشف DeepGuard التزييف؟",
  sec1_sub: "أربعة كواشف مستقلة تفحص كل صورة، ثم يُدمَج حكمها في نتيجة واحدة.",
  sig1_name: "بصمة المصدر (C2PA)",
  sig1_badge: "دليل قاطع",
  sig1_desc: "تقرأ شهادة المصدر الموقّعة المضمّنة في الملف إن وُجدت، فتثبت أصالة الصورة مباشرة.",
  sig2_name: "تحليل المشهد",
  sig2_badge: "الصورة كاملة",
  sig2_desc: "كاشف مفتوح المصدر مدرَّب على 2.7 مليون صورة يفحص الصورة كاملة، من الحصان إلى السماء والبشر.",
  sig3_name: "متخصص الوجوه",
  sig3_badge: "الوجوه",
  sig3_desc: "يركّز على الوجوه المقتطعة ويكشف علامات التوليد الدقيقة فيها.",
  sig4_name: "حارس الصور الحقيقية",
  sig4_badge: "الدرع",
  sig4_desc: "يحمي الصور الأصلية من الإدانة الخاطئة ويخفض نسبة الإنذارات الكاذبة.",

  // Pipeline — five steps
  sec2_title: "كيف يعمل الفحص؟",
  sec2_sub: "خمس خطوات متسلسلة من الملف الخام إلى الحكم النهائي.",
  pipe1_t: "فحص البيانات الوصفية",
  pipe1_d: "نقرأ شهادة المصدر والبيانات التقنية داخل الملف قبل أي شيء آخر.",
  pipe2_t: "التحقق من جودة العينة",
  pipe2_d: "نقيس الدقة والضغط والوضوح، ونرفع عتبة الحكم في الصور الضعيفة تلقائيًا.",
  pipe3_t: "الاستدلال بأربعة كواشف بالتوازي",
  pipe3_d: "تفحص الكواشف الأربعة الصورة نفسها في الوقت ذاته، ويصوّت كل كاشف مستقلاً.",
  pipe4_t: "دمج النتائج بأوزان ذكية",
  pipe4_d: "يُوزَن صوت كل كاشف بحسب قوته، فلا يحسم صوت واحد حكمًا مشكوكًا فيه.",
  pipe5_t: "حكم نهائي مع الدليل",
  pipe5_d: "تحصل على الحكم مع شرح مباشر للأدلة التي أدت إليه.",

  // Verdict slider — bands 0–35 / 35–65 / 65–100
  sec3_title: "ثلاثة أحكام بدل التخمين",
  sec3_sub: "حرّك المؤشر وشاهد كيف يتبدّل الحكم فورًا بين ثلاث حالات واضحة.",
  sim_title: "جرّب منطق الحكم بنفسك",
  sim_sub: "حرّك المؤشر لتغيير احتمالية التزييف، وشاهد الحكم يتبدّل مباشرة:",
  sim_label_fake: "مزيفة",
  sim_label_uncertain: "تحتاج مراجعة",
  sim_label_real: "أصلية",
  sim_band_real: "0–35% أصلية",
  sim_band_review: "35–65% مراجعة",
  sim_band_fake: "65–100% مزيفة",
  sim_axis_l: "0% أصلية",
  sim_axis_r: "100% مزيفة",
  sim_desc_fake: "المؤشرات تجاوزت عتبة الثقة — الكواشف أجمعت على مؤشرات توليد واضحة.",
  sim_desc_uncertain: "الأدلة غير كافية لحسم الحكم — نفضّل الإحالة إلى المراجعة على التخمين.",
  sim_desc_real: "المؤشرات منخفضة — لا توجد آثار توليد أو تلاعب في العينة.",
  sim_aria: "محاكي احتمالية التزييف",
  sim_honesty_note: "نطاق «تحتاج مراجعة» ليس ضعفًا، بل صدق هندسي يمنع اتهام الأبرياء.",

  // FAQ — accordion
  sec4_title: "الأسئلة الشائعة",
  sec4_sub: "إجابات مباشرة وواضحة.",
  faq1_q: "هل تغادر صوري جهازي؟",
  faq1_a: "لا. يجري الفحص بالكامل على جهازك، ولا تُرسَل أي صورة إلى خدمة خارجية ولا نحتفظ بها بعد الفحص.",
  faq2_q: "لماذا تظهر نتيجة «تحتاج مراجعة»؟",
  faq2_a: "لأن الأدلة غير كافية لحكم موثوق، فنفضّل الصدق على التخمين.",
  faq3_q: "ماذا لو كان الوجه صغيرًا أو بعيدًا في الصورة؟",
  faq3_a: "تنخفض دقة متخصص الوجوه، فيعتمد النظام تلقائيًا على بقية الكواشف.",
  faq4_q: "ما الفرق بين C2PA والتحليل البصري؟",
  faq4_a: "C2PA شهادة مصدر موقّعة داخل الملف، أما التحليل البصري فيفحص محتوى البكسلات.",
  faq5_q: "هل هناك حد أدنى لجودة الصورة؟",
  faq5_a: "نعم، الصور شديدة الضغط أو الصغيرة جدًا تُرفع عتبة الإدانة فيها لتفادي الأحكام الخاطئة.",

  // Final CTA + footer
  cta_title: "جرّب DeepGuard الآن",
  cta_sub: "ارفع صورة واحصل على حكم واضح مدعوم بالدليل، دون أن تغادر الصورة جهازك.",
  cta_btn: "افتح منصة الفحص",
  footer_tag: "DeepGuard · كشف جنائي محلي للصور",
  footer_rights: "جميع الحقوق محفوظة",

  // Dashboard (page.tsx)
  dash_tagline: "كشف التزوير العميق والفحوص الجنائية للوسائط",
  dash_about: "عن المحرك",
  dash_backend_on: "المحرك الخلفي: FastAPI V3 يعمل",
  dash_docs: "توثيق FastAPI",
  dash_h1: "فحص التزييف العميق وتحرير الوسائط",
  dash_h1_sub:
    "ارفع أي صورة لفحص التوليد بالشبكات العصبية، والحشو بالانتشار، وخيوط دمج الوجوه — واحصل على تقرير جنائي موثّق.",
  dash_badge: "Next.js 14 + FastAPI + لجنة كواشف مستقلة",
  dash_demo_fake: "تجربة عينة مزيفة",
  dash_demo_real: "تجربة عينة أصيلة",
  feat1_t: "محرك الكشف رباعي الإشارات",
  feat1_d:
    "فحص بايتات المصدر (C2PA)، فورنسيّات المشهد المدرَّبة على 4,803 مولّد، متخصص وجوه، ومتحكّم رابع — تُدمَج بتحكيم موزون مع بوابة جودة.",
  feat2_t: "مصفوفة فورنسيّة خماسية الأبعاد",
  feat2_d:
    "تحليل مستويات الخطأ (ELA)، ضوضاء عالية التردد، تشتّت القنوات اللونية، سلامة الحدود، وتشوّه الوجه — مقاييس حقيقية لا مجرد مؤشرات.",
  feat3_t: "تقارير PDF موثّقة",
  feat3_d:
    "توليد تلقائي للتقرير مع معرّف specimen، ملخص تنفيذي، وسلسلة عهدة للملف — جاهز للاستخدام الرسمي.",
  dash_footer_api: "الواجهة الخلفية:",
  dash_footer_pdf: "تصدير PDF:",

  // UploadZone
  up_drop_title_pre: "اسحب وأفلت صورة هنا، أو ",
  up_drop_link: "تصفّح",
  up_drop_formats: "يدعم JPG وPNG وWEBP وGIF بجودة عالية حتى 20MB",
  up_chip1: "معالجة عصبية مسبقة (299×299)",
  up_chip2: "بصمات فورنسيّة متعددة الطبقات",
  up_loaded_pre: "تم تحميل العينة: ",
  up_change: "تغيير",
  up_another: "اضغط أو أفلت صورة أخرى لفحص عينة جديدة",
  up_alert_invalid: "الرجاء رفع ملف صورة صالح (JPG, PNG, WEBP, GIF).",

  // ResultCard
  rc_verdict: "حكم التصنيف",
  rc_engine: "C2PA + لجنة كواشف مستقلة + تحكيم",
  rc_uncertain: "غير حاسم — يلزم مراجعة",
  rc_fake: "تزييف اصطناعي مكتشف",
  rc_real: "عينة أصيلة",
  rc_confidence: "درجة الثقة",
  rc_fake_prob: "احتمالية التزييف الاصطناعي",
  rc_fake_note: "احتمال وجود آثار توليد بالشبكات، أو نماذج الانتشار، أو استبدال الوجوه.",
  rc_real_prob: "احتمالية الأصالة",
  rc_real_note: "تماسك مع ضوضاء مستشعر الكاميرا الطبيعية والبصريات غير المضغوطة.",

  // MultiAspectChart
  mc_title: "التفصيل الفورنسي متعدد الجوانب",
  mc_sub: "خمسة فحوص مكانية وترددية",
  mc_lighting: "الإضاءة وتباين الانعكاسات",
  mc_lighting_d: "تدرّج الإضاءة الاتجاهي ومواءمة الانعكاسات عبر العينين وجسر الأنف.",
  mc_texture: "تماسك النسيج الدقيق",
  mc_texture_d: "بنية مسام الجلد عالية التردد مقابل التنعيم الاصطناعي للشبكات التوليدية.",
  mc_color: "تشتّت الفضاء اللوني",
  mc_color_d: "الانحراف المعياري بين قنوات RGB وتماسك الإشارة اللونية.",
  mc_background: "سلامة الحدود والخلفية",
  mc_background_d: "انتقالات الحواف، والاهتزاز، وخيوط الدمج عند المحيط.",
  mc_face: "تناظر الوجه والتشوه",
  mc_face_d: "كشف اعوجاج استبدال الوجوه العصبي، وتناظر الأذن، واصطفاف الأسنان.",
  st_none: "لا بيانات",
  st_high: "شذوذ مرتفع",
  st_elevated: "مرتفع",
  st_nominal: "طبيعي",

  // ForensicReport
  fr_title: "نتائج التحليل الفورنسي",
  fr_sub: "بصمات آلية، تناقضات بصرية، وإسناد المصدر",
  fr_copy: "نسخ",
  fr_copied: "تم النسخ",
  fr_export: "تصدير تقرير PDF",
  fr_generating: "جارٍ توليد PDF...",
  fr_report_id: "معرّف التقرير:",
  fr_coc: "سلسلة عهدة: عينة موثّقة بـ SHA-256",
  fr_copy_fail: "فشل تنزيل التقرير. تأكد من تشغيل المحرك الخلفي.",

  // ScanAnimation + ScanningImage
  sa_corridor: "ممر الفحص الجنائي — مباشر",
  sa_phase_bytes: "فحص بصمات المصدر",
  sa_phase_detect: "استدلال لجنة الكواشف",
  sa_phase_face: "تحليل آثار الوجه",
  sa_phase_quality: "تقييم جودة العينة",
  sa_phase_fuse: "دمج الإشارات والتحكيم",
  sa_phase_report: "توليد الحكم الجنائي",
  sa_done: "تم",
  sa_run: "يعمل",
  sa_queued: "بالانتظار",
  si_grid_note: "تحليل شبكي · مسح متدرّج",
  si_percent: "جارٍ الفحص",

  // Deep analysis (sources/dates/logic/agenda)
  deep_title: "التحليل المعمّق",
  deep_source: "المصادر",
  deep_source_sub: "روابط قابلة للفحص ومصادر معلومة",
  deep_date: "التواريخ",
  deep_date_sub: "تواريخ مستحيلة أو غائبة أو قديمة مُباعة كعاجل",
  deep_logic: "المنطق",
  deep_logic_sub: "مطلقات ومؤطرات لا يمكن دحضها وخوف بلا دليل",
  deep_agenda: "الأجندة",
  deep_agenda_sub: "تأمر، ثنائية نحن/هم، إغراء مالي، تحريض",
  deep_low: "سليم",
  deep_mid: "مشكوك",
  deep_high: "خطير",

  // Language toggle
  lang_toggle_title: "تغيير اللغة",

  // Mode toggle (image forensics / news misinformation)
  mode_image: "تحليل صورة",
  mode_news: "تحري خبر",
  mode_toggle_aria: "تبديل وضع الفحص",

  // News analysis UI
  news_h1: "تحري الأخبار من لقطة الشاشة",
  news_h1_sub:
    "ارفع لقطة شاشة للخبر: نستخرج النص (OCR عربي/إنجليزي)، نحلل أساليب التلاعب، نفحص الصورة فورنسيّاً، ونتحقق من الادعاءات في قواعد التحقق العالمية — وحكم واحد بسجل أدلة.",
  news_badge: "OCR + تحليل لغوي + تحقق خارجي",
  news_demo: "تجربة خبر مثير",
  news_extracted: "النص المستخرج من الصورة",
  news_no_text: "لم يُستخرج نص — قد تكون الصورة خالية من نصوص أو جودة OCR غير كافية",
  news_misinfo_prob: "احتمالية التضليل",
  news_verdict_misleading: "خبر مضلل",
  news_verdict_suspicious: "مشتبه به — يلزم تدقيق",
  news_verdict_likely_fine: "لا مؤشرات تضليل واضحة",
  news_signals_title: "تفصيل الإشارات",
  news_signal_text: "التحليل اللغوي",
  news_signal_forensic: "فورنسيّات الصورة",
  news_signal_factcheck: "التحقق الخارجي",
  news_fc_ok: "نتائج مطابقة",
  news_fc_no_coverage: "لا تغطية لهذا الادعاء",
  news_fc_unavailable: "غير مفعّل/غير متاح",
  news_fc_disabled: "معطّل",
  news_fc_disputed: "ادعاءات مكذّبة موثّقة",
  news_fc_verified: "ادعاءات موثّقة صحيحة",
  news_fc_view: "عرض المصدر",
  news_cues_title: "مؤشرات التلاعب المرصودة",
  news_cue_urgency: "استعجال وإلحاح مصطنع",
  news_cue_engagement: "تحريض على المشاركة",
  news_cue_authority: "ادعاءات بلا مصدر",
  news_cue_shock: "استثارة عاطفية",
  news_cue_questions: "كثافة استفهام استفزازي",
  news_cue_families: "عائلات إشارات",
  news_audit_title: "سجل التحكيم",
  news_engine_note: "محرك تحري الأخبار V1 — حكم بالأدلة لا بالانطباع",

  // ---- Investigation report (m4+) -------------------------------------
  // Section headers (mono uppercase via CSS)
  sec_verdict: "حُكمُنا",
  sec_scores: "درجات نماذج الكشف",
  sec_map: "خريطة التلاعب",
  sec_technical: "المعلومات التقنية",
  sec_pipeline: "خط التحليل",
  sec_how_we_know: "كيف عرفنا ذلك",
  sec_c2pa: "C2PA / بيانات الاعتماد",
  sec_spot_diff: "التمييز بين الصور",
  sec_whats_in_image: "ما في هذه الصورة",
  sec_what_to_do: "ماذا تفعل بعد ذلك",
  sec_links_web: "روابط على الويب",
  sec_fact_check: "مراقبة التحقق",
  sec_reverse_search: "بحث الصور العكسي",
  sec_location: "تحليل الموقع",
  sec_further: "مزيد من التحقيق",
  sec_ask: "اسأل عن هذه الصورة",
  sec_was_correct: "هل كانت النتيجة صحيحة؟",
  sec_ai_visual: "نتائج التحليل البصري",
  sec_research: "أبحاث",
  back_to_verdict: "العودة إلى الحكم",
  card_collapse: "طيّ",
  card_expand: "توسيع",
  state_ok: "تم الفحص",
  state_loading: "جارٍ التحميل",
  state_skipped: "متجاوَز",
  state_not_applicable: "لا ينطبق",
  state_error: "خطأ",
  state_not_implemented: "غير منفَّذ بعد",

  // Verdict labels (backend fixed set)
  v_ai_detected: "تم رصد الذكاء الاصطناعي",
  v_possible_edits: "تعديلات محتملة",
  v_investigate: "يستوجب تحقيقًا",
  v_no_ai: "لا دليل على الذكاء الاصطناعي",

  // Axes
  axis_ai_gen: "التوليد بالذكاء الاصطناعي",
  axis_editing: "فحص التعديل",
  axis_source: "فحص المصدر",
  axis_clear: "سليم",
  axis_flag: "إنذار",

  // Verdict card
  vd_badge_type: "نوع الفحص",
  vd_badge_generation: "كشف التوليد بالذكاء الاصطناعي",
  vd_badge_editing: "فحص التعديل (خوارزمي)",
  vd_badge_source: "فحص المصدر",
  vd_should_know: "ما يجب أن تعرفه",
  vd_disclaimer: "هذه الإشارات تدعم قرارًا — وليست دليلًا قاطعًا. غياب التحذير لا يثبت أصالة الصورة.",
  vd_reasoning: "اعرض التحليل الكامل",
  vd_copy: "نسخ الحكم",
  vd_copied: "تم النسخ إلى الحافظة",
  vd_copy_failed: "فشل النسخ — حدّد النص يدويًا",
  vd_why: "لماذا هذا الحكم",
  vd_human: "ملاحظة إنسانية مهمة",
  vd_computer: "ما يراه الحاسوب",
  vd_web: "الحضور على الويب",
  vd_not_checked: "لم يُفحص بعد",
  vd_narrative: "السرد الجنائي",
  vd_privacy: "الخصوصية: يجري هذا التحليل على خادمك المحلي، ولا تُرسل الصورة إلى أي خدمة خارجية.",
  vd_disagreement: "لم تتفق كل الكواشف — والاختلاف معروض أعلاه.",
  vd_no_disagreement: "اتجهت كل الكواشف في الاتجاه نفسه.",

  // Narrative templates (interpolated in the component)
  n_no_exif: "لا بيانات EXIF — لا بصمة كاميرا (شائع في لقطات الشاشة والصور المصدَّرة والمولَّدة بالذكاء الاصطناعي).",
  n_exif: "توجد EXIF: كاميرا {camera}، بتاريخ {date}.",
  n_c2pa_gen: "بيانات الاعتماد تعلن توليدًا بالذكاء الاصطناعي (المولِّد: {generator}).",
  n_generator_sig: "توقيعات المولِّد وُجدت داخل بيانات الملف: {list}.",
  n_models_clear: "لم يتجاوز أي كاشف عتبة الإنذار.",
  n_hash_match: "التجزئات الإدراكية تطابق سجلًا في قاعدة بيانات تزييف معروفة.",
  n_quality: "فئة جودة العينة: {tier} — شريط الإنذار يضبط نفسه تلقائيًا مع الصور الضعيفة.",
  n_signals: "رصد {flagged} من {total} كواشف إنذارًا، وسُيّف {clear}.",

  // Model scores card
  ms_prob: "احتمال التوليد بالذكاء الاصطناعي",
  ms_kind_generation: "كاشف توليد",
  ms_role_primary: "رئيسي",
  ms_role_supporting: "داعم",
  ms_outlier: "يخالف الأغلبية",
  ms_call_flag: "إنذار",
  ms_call_clear: "سليم",
  ms_call_uncertain: "غير محسوم",
  ms_no_editing: "لا نموذج تعديل مسجَّل — حكم «تعديلات محتملة» يبقى محجوزًا.",
  ms_error_generic: "فشل الكاشف",
  ms_not_loaded: "النموذج غير محمَّل",
  ms_no_vote: "لا تصويت لهذه الصورة",
  ms_bands_note: "النطاقات تعيد استخدام عتبات المحرك الحالية (إنذار فوق الشريط المشروط بالجودة، وسليم تحت الشريط الفعلي).",

  // Manipulation map card
  mm_original: "الأصلية",
  mm_ela: "خريطة حرارة ELA",
  mm_blend: "الدمج",
  mm_opacity: "شفافية الطبقة",
  mm_ela_note: "ELA يُبرز المناطق ذات خطأ إعادة ضغط غير معتاد — أداة تحديد محلي لتعديلات محتملة.",
  mm_no_editing_model: "لا نموذج تعديل مسجَّل، لذا لا يُدّعى نوع تلاعب — الخريطة تعتمد على ELA فقط ولا تغيّر الحكم.",
  mm_unavailable: "الخريطة الحرارية غير متاحة لهذه الصورة.",

  // Report shell
  rep_analyze_another: "حلّل صورة أخرى",
  rep_verdict_dot: "الحكم الحالي",

  // Research card (m5)
  res_open_link: "فتح الرابط في تبويب جديد",
  res_query: "الاستعلام",
  res_coords: "الإحداثيات",
  res_rule: "مصدر الإرشاد",

  // Language toggle
} as const;

export type DictKey = keyof typeof ar;

const en: Record<DictKey, string> = {
  // Landing — hero
  hero_title: "Detect fake images with confidence",
  hero_sub: "DeepGuard examines every image with four independent detectors and gives you a clear, evidence-backed verdict — entirely on your device, with no uploads.",
  cta_start: "Start a scan",
  cta_how: "How it works",
  nav_open: "Open platform",
  nav_features: "Features",
  nav_signals: "How it works",
  nav_how: "The pipeline",
  nav_sim: "Try the verdict",
  nav_faq: "FAQ",
  trust_local: "Runs locally",
  trust_noupload: "No uploads",
  trust_evidence: "Evidence-backed verdict",

  // Stats strip — 4 equal cards
  stat1_v: "4,803",
  stat1_l: "generators the detector was trained against",
  stat2_v: "4",
  stat2_l: "independent detectors running in parallel",
  stat3_v: "0",
  stat3_l: "images ever leave your device",
  stat4_v: "100%",
  stat4_l: "local analysis, end to end",

  // Detectors — 2×2 cards
  sec1_title: "How DeepGuard detects fakes",
  sec1_sub: "Four independent detectors examine every image, and their verdicts fuse into one result.",
  sig1_name: "Source fingerprint (C2PA)",
  sig1_badge: "Hard proof",
  sig1_desc: "Reads the signed provenance certificate embedded in the file, when present, to confirm authenticity outright.",
  sig2_name: "Scene analysis",
  sig2_badge: "Whole image",
  sig2_desc: "An open-source detector trained on 2.7 million images that reads the entire scene — horse, sky and people alike.",
  sig3_name: "Face specialist",
  sig3_badge: "Faces",
  sig3_desc: "Focuses on cropped faces and catches the subtle artifacts generation leaves behind.",
  sig4_name: "Real-photo guardian",
  sig4_badge: "The shield",
  sig4_desc: "Protects genuine photos from false accusations and keeps false alarms low.",

  // Pipeline — five steps
  sec2_title: "How a scan works",
  sec2_sub: "Five sequential steps, from raw file to final verdict.",
  pipe1_t: "Metadata scan",
  pipe1_d: "We read the provenance certificate and technical metadata inside the file first.",
  pipe2_t: "Sample quality check",
  pipe2_d: "We measure resolution, compression and sharpness, and automatically raise the bar on weak images.",
  pipe3_t: "Four detectors in parallel",
  pipe3_d: "All four detectors examine the same image at once, and each votes independently.",
  pipe4_t: "Smart weighted fusion",
  pipe4_d: "Each vote is weighted by its strength, so no single vote can settle a doubtful verdict.",
  pipe5_t: "Final verdict with evidence",
  pipe5_d: "You get the verdict plus a direct explanation of the evidence behind it.",

  // Verdict slider — bands 0-35 / 35-65 / 65-100
  sec3_title: "Three verdicts, no guessing",
  sec3_sub: "Move the slider and watch the verdict switch instantly between three clear states.",
  sim_title: "Try the verdict logic yourself",
  sim_sub: "Drag the slider to change the fake probability and watch the verdict switch live:",
  sim_label_fake: "FAKE",
  sim_label_uncertain: "NEEDS REVIEW",
  sim_label_real: "AUTHENTIC",
  sim_band_real: "0-35% authentic",
  sim_band_review: "35-65% review",
  sim_band_fake: "65-100% fake",
  sim_axis_l: "0% authentic",
  sim_axis_r: "100% fake",
  sim_desc_fake: "The signals crossed the confidence threshold — detectors agree on clear generation artifacts.",
  sim_desc_uncertain: "The evidence is not enough for a reliable call — we refer it for review rather than guess.",
  sim_desc_real: "Signals are low — no generation or tampering artifacts in this sample.",
  sim_aria: "Fake probability simulator",
  sim_honesty_note: "The \"needs review\" band is not weakness — it's engineering honesty that protects the innocent.",

  // FAQ — accordion
  sec4_title: "Frequently asked questions",
  sec4_sub: "Direct, clear answers.",
  faq1_q: "Do my images leave my device?",
  faq1_a: "No. The entire scan runs on your device — no image is sent to any external service, and nothing is retained afterwards.",
  faq2_q: "Why do I get a \"needs review\" result?",
  faq2_a: "Because the evidence isn't enough for a reliable verdict — we prefer honesty over guessing.",
  faq3_q: "What if the face is small or distant in the photo?",
  faq3_a: "The face specialist's accuracy drops, so the system automatically relies on the other detectors.",
  faq4_q: "What's the difference between C2PA and visual analysis?",
  faq4_a: "C2PA is a signed source certificate inside the file, while visual analysis examines the actual pixels.",
  faq5_q: "Is there a minimum image quality?",
  faq5_a: "Yes — heavily compressed or very small images get a raised conviction threshold to avoid wrong verdicts.",

  // Final CTA + footer
  cta_title: "Try DeepGuard now",
  cta_sub: "Upload an image and get a clear, evidence-backed verdict — without the image ever leaving your device.",
  cta_btn: "Open the platform",
  footer_tag: "DeepGuard · Local forensic image analysis",
  footer_rights: "All rights reserved",

dash_tagline: "Deepfake detection & media forensics",
  dash_about: "About the engine",
  dash_backend_on: "Backend: FastAPI Engine V3 Active",
  dash_docs: "FastAPI Docs",
  dash_h1: "Deepfake & Media Forgery Inspection",
  dash_h1_sub:
    "Upload any image to scan for GAN generation, diffusion inpainting and face-swap blending seams — with a certified forensic report.",
  dash_badge: "Next.js 14 + FastAPI + independent detector panel",
  dash_demo_fake: "Test synthetic demo",
  dash_demo_real: "Test authentic demo",
  feat1_t: "Four-Signal Detection Engine",
  feat1_d:
    "Provenance byte scan (C2PA), scene forensics trained on 4,803 generators, a face specialist, and a fourth arbiter — fused by weighted adjudication with a quality gate.",
  feat2_t: "5-Aspect Forensic Matrix",
  feat2_d:
    "Error level analysis, high-frequency noise, chroma dispersion, boundary integrity and facial distortion — real measurements, not placeholder indicators.",
  feat3_t: "Certified PDF Reports",
  feat3_d:
    "Automated report generation with a specimen ID, executive summary and chain-of-custody notes — ready for official use.",
  dash_footer_api: "FastAPI Backend:",
  dash_footer_pdf: "PDF Export:",

  up_drop_title_pre: "Drag & drop an image here, or ",
  up_drop_link: "browse",
  up_drop_formats: "Supports high-resolution JPG, PNG, WEBP, GIF up to 20MB",
  up_chip1: "Neural preprocessing (299×299)",
  up_chip2: "Multi-layer forensic fingerprints",
  up_loaded_pre: "Specimen loaded: ",
  up_change: "Change",
  up_another: "Click or drop another image to analyze a new specimen",
  up_alert_invalid: "Please upload a valid image file (JPG, PNG, WEBP, GIF).",

  rc_verdict: "Classification Verdict",
  rc_engine: "C2PA + independent detector panel + adjudication",
  rc_uncertain: "UNCERTAIN — REVIEW REQUIRED",
  rc_fake: "SYNTHETIC / DEEPFAKE DETECTED",
  rc_real: "AUTHENTIC SPECIMEN",
  rc_confidence: "Confidence Level",
  rc_fake_prob: "Synthetic / Fake Probability",
  rc_fake_note: "Likelihood of GAN, diffusion, or face-swap manipulation markers.",
  rc_real_prob: "Authentic / Real Probability",
  rc_real_note: "Coherence with natural camera sensor noise and uncompressed optics.",

  mc_title: "Multi-Aspect Forensic Breakdown",
  mc_sub: "5 dimensional spatial & frequency checks",
  mc_lighting: "Lighting & Specular Variance",
  mc_lighting_d: "Directional luminance falloff and specular reflection alignment across eyes and nose bridge.",
  mc_texture: "Micro-Texture Coherence",
  mc_texture_d: "High-frequency dermal pore structures vs GAN artificial smoothing.",
  mc_color: "Color Space Dispersion",
  mc_color_d: "Inter-channel RGB standard deviation and chrominance consistency.",
  mc_background: "Boundary & Background Integrity",
  mc_background_d: "Edge transition interpolation, jitter, and perimeter blending seams.",
  mc_face: "Facial Symmetry & Distortion",
  mc_face_d: "Neural face-swap warping detection, earlobe symmetry, and teeth alignment.",
  st_none: "No Data",
  st_high: "High Anomaly",
  st_elevated: "Elevated",
  st_nominal: "Nominal",

  fr_title: "Forensic Intelligence Findings",
  fr_sub: "Automated forensic fingerprints, optical inconsistencies & attribution",
  fr_copy: "Copy",
  fr_copied: "Copied",
  fr_export: "Export PDF Report",
  fr_generating: "Generating PDF...",
  fr_report_id: "Report ID:",
  fr_coc: "Chain-of-Custody: SHA-256 Verified Specimen",
  fr_copy_fail: "Downloading report failed. Please ensure the backend is available.",

  sa_corridor: "FORENSIC CORRIDOR — LIVE",
  sa_phase_bytes: "Provenance byte scan",
  sa_phase_detect: "Detector panel inference",
  sa_phase_face: "Facial artifact analysis",
  sa_phase_quality: "Specimen quality gate",
  sa_phase_fuse: "Signal fusion & adjudication",
  sa_phase_report: "Forensic verdict synthesis",
  sa_done: "DONE",
  sa_run: "RUN",
  sa_queued: "QUEUED",
  si_grid_note: "GRID ANALYSIS · TIERED SWEEP",
  si_percent: "SCANNING",

  // Mode toggle (image forensics / news misinformation)
  mode_image: "Image forensics",
  mode_news: "News check",
  mode_toggle_aria: "Toggle scan mode",

  // News analysis UI
  news_h1: "News screenshot fact-check",
  news_h1_sub:
    "Upload a news screenshot: we extract the text (ar/en OCR), analyze manipulation tactics, run image forensics, and check claims against global fact-check databases — one verdict with a full evidence log.",
  news_badge: "OCR + language analysis + external fact-check",
  news_demo: "Test sensational demo",
  news_extracted: "Text extracted from image",
  news_no_text: "No text extracted — the image may contain no text or OCR quality was insufficient",
  news_misinfo_prob: "Misinformation probability",
  news_verdict_misleading: "MISLEADING NEWS",
  news_verdict_suspicious: "SUSPICIOUS — REVIEW ADVISED",
  news_verdict_likely_fine: "NO CLEAR MANIPULATION",
  news_signals_title: "Signal breakdown",
  news_signal_text: "Language analysis",
  news_signal_forensic: "Image forensics",
  news_signal_factcheck: "External fact-check",
  news_fc_ok: "Matching results",
  news_fc_no_coverage: "No coverage for this claim",
  news_fc_unavailable: "Unavailable",
  news_fc_disabled: "Disabled",
  news_fc_disputed: "documented disputed claims",
  news_fc_verified: "documented verified claims",
  news_fc_view: "View source",
  news_cues_title: "Detected manipulation cues",
  news_cue_urgency: "Artificial urgency",
  news_cue_engagement: "Engagement bait",
  news_cue_authority: "Unsourced authority claims",
  news_cue_shock: "Emotional shock tactics",
  news_cue_questions: "Intrigue question density",
  news_cue_families: "signal families",
  news_audit_title: "Adjudication log",
  news_engine_note: "News Verification Engine V1 — evidence over vibes",

  lang_toggle_title: "Switch language",

  // Deep analysis (sources/dates/logic/agenda)
  deep_title: "Deep analysis",
  deep_source: "Sources",
  deep_source_sub: "Checkable links and named institutions",
  deep_date: "Dates",
  deep_date_sub: "Impossible, missing, or stale dates sold as breaking",
  deep_logic: "Logic",
  deep_logic_sub: "Absolutist overreach, unfalsifiable framing, fear without evidence",
  deep_agenda: "Agenda",
  deep_agenda_sub: "Conspiracy, us-vs-them, financial bait, incitement",
  deep_low: "Sound",
  deep_mid: "Dubious",
  deep_high: "Severe",

  // ---- Investigation report (m4+) -------------------------------------
  sec_verdict: "OUR VERDICT",
  sec_scores: "DETECTION MODEL SCORES",
  sec_map: "MANIPULATION MAP",
  sec_technical: "TECHNICAL INFO",
  sec_pipeline: "ANALYSIS PIPELINE",
  sec_how_we_know: "HOW WE KNOW",
  sec_c2pa: "C2PA / CONTENT CREDENTIALS",
  sec_spot_diff: "SPOT THE DIFFERENCE",
  sec_whats_in_image: "WHAT'S IN THIS IMAGE",
  sec_what_to_do: "WHAT TO DO NEXT",
  sec_links_web: "LINKS ON THE WEB",
  sec_fact_check: "FACT-CHECK MONITOR",
  sec_reverse_search: "REVERSE IMAGE SEARCH",
  sec_location: "LOCATION ANALYSIS",
  sec_further: "FURTHER INVESTIGATION",
  sec_ask: "ASK ABOUT THIS IMAGE",
  sec_was_correct: "WAS THIS RESULT CORRECT?",
  sec_ai_visual: "AI VISUAL ANALYSIS FINDINGS",
  sec_research: "RESEARCH",
  back_to_verdict: "Back to verdict",
  card_collapse: "Collapse",
  card_expand: "Expand",
  state_ok: "Checked",
  state_loading: "Loading",
  state_skipped: "Skipped",
  state_not_applicable: "Not applicable",
  state_error: "Error",
  state_not_implemented: "Not implemented yet",

  v_ai_detected: "AI Detected",
  v_possible_edits: "Possible Edits",
  v_investigate: "Investigate",
  v_no_ai: "No AI Detected",

  axis_ai_gen: "AI Generation",
  axis_editing: "Editing Check",
  axis_source: "Source Check",
  axis_clear: "clear",
  axis_flag: "flag",

  vd_badge_type: "Detection type",
  vd_badge_generation: "AI generation detection",
  vd_badge_editing: "Editing check (algorithmic)",
  vd_badge_source: "Source inspection",
  vd_should_know: "HERE IS WHAT YOU SHOULD KNOW",
  vd_disclaimer: "These signals support a decision — they are not conclusive proof. Absence of a warning does not prove authenticity.",
  vd_reasoning: "See the full reasoning",
  vd_copy: "Copy verdict",
  vd_copied: "Copied to clipboard",
  vd_copy_failed: "Copy failed — select the text manually",
  vd_why: "WHY THIS VERDICT",
  vd_human: "What a human should note",
  vd_computer: "What the computer sees",
  vd_web: "Web presence",
  vd_not_checked: "not checked yet",
  vd_narrative: "FORENSIC NARRATIVE",
  vd_privacy: "Privacy: this analysis runs on your local server; the image is not sent to any external service.",
  vd_disagreement: "The detectors did not fully agree — the disagreement is shown above.",
  vd_no_disagreement: "All detectors leaned the same way.",

  n_no_exif: "No EXIF metadata — no camera fingerprint (common for screenshots, exports and AI-generated images).",
  n_exif: "EXIF present: camera {camera}, date {date}.",
  n_c2pa_gen: "Content Credentials declare AI generation (generator: {generator}).",
  n_generator_sig: "Generator signatures found inside the file metadata: {list}.",
  n_models_clear: "No detector crossed the alert threshold.",
  n_hash_match: "Perceptual hashes match a known-forgery database entry.",
  n_quality: "Specimen quality tier: {tier} — the alert bar adjusts automatically for weak images.",
  n_signals: "{flagged} of {total} detectors alerted; {clear} cleared.",

  ms_prob: "Probability of AI generation",
  ms_kind_generation: "generation detector",
  ms_role_primary: "primary",
  ms_role_supporting: "supporting",
  ms_outlier: "differs from the majority",
  ms_call_flag: "flags",
  ms_call_clear: "clear",
  ms_call_uncertain: "uncertain",
  ms_no_editing: "No editing model is registered — the Possible Edits verdict stays reserved.",
  ms_error_generic: "Detector failed",
  ms_not_loaded: "Model not loaded",
  ms_no_vote: "No vote for this image",
  ms_bands_note: "Bands reuse the engine's existing thresholds (flag above the quality-gated bar, clear below the real bar).",

  mm_original: "Original",
  mm_ela: "ELA heat map",
  mm_blend: "Blend",
  mm_opacity: "Layer opacity",
  mm_ela_note: "ELA highlights regions with unusual recompression error — a localisation aid for possible edits.",
  mm_no_editing_model: "No editing model is registered, so no manipulation type is claimed — the map is ELA-only and does not change the verdict.",
  mm_unavailable: "Heat map unavailable for this image.",

  rep_analyze_another: "Analyze another image",
  rep_verdict_dot: "Current verdict",

  // Research card (m5)
  res_open_link: "Open link in a new tab",
  res_query: "Query",
  res_coords: "Coordinates",
  res_rule: "Guidance source",
};

const dicts: Record<Lang, Record<DictKey, string>> = { ar, en };

/* ------------------------------------------------------------------ */
/*  Context + provider                                                 */
/* ------------------------------------------------------------------ */

interface LangCtx {
  lang: Lang;
  dir: "rtl" | "ltr";
  setLang: (l: Lang) => void;
  t: (k: DictKey) => string;
}

const LanguageContext = createContext<LangCtx>({
  lang: "ar",
  dir: "rtl",
  setLang: () => {},
  t: (k) => ar[k],
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ar");

  // persist + restore
  useEffect(() => {
    const saved = window.localStorage.getItem("dg-lang");
    if (saved === "en" || saved === "ar") setLangState(saved);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    window.localStorage.setItem("dg-lang", lang);
  }, [lang]);

  const setLang = (l: Lang) => setLangState(l);
  const t = (k: DictKey) => dicts[lang][k] ?? ar[k];

  return (
    <LanguageContext.Provider value={{ lang, dir: lang === "ar" ? "rtl" : "ltr", setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLang() {
  return useContext(LanguageContext);
}

/* ------------------------------------------------------------------ */
/*  Language toggle — Cyber Gooey segmented control.                   */
/*  SVG gooey filter turns the single sliding neon bubble into a       */
/*  liquid blob. Fixed 128×40, click-anywhere toggle, LTR-fixed math.  */
/* ------------------------------------------------------------------ */

export function LanguageToggle({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useLang();
  const isArabic = lang === "ar";

  return (
    <div className={`relative inline-flex items-center shrink-0 ${className}`}>
      {/* SVG liquid filter — defined once, referenced by the gooey layer */}
      <svg className="absolute w-0 h-0" xmlns="http://www.w3.org/2000/svg" version="1.1" aria-hidden="true">
        <defs>
          <filter id="cyber-gooey" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
            <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9" result="gooey" />
            <feComposite in="SourceGraphic" in2="gooey" operator="atop" />
          </filter>
        </defs>
      </svg>

      <button
        type="button"
        onClick={() => setLang(isArabic ? "en" : "ar")}
        title={t("lang_toggle_title")}
        aria-label={t("lang_toggle_title")}
        aria-pressed={isArabic}
        dir="ltr"
        className="relative flex items-center w-[128px] h-[40px] p-1 bg-[#080c10] border border-[#122b20] rounded-full cursor-pointer focus:outline-none select-none overflow-hidden hover:border-[#00ff9d]/30 transition-colors"
        // Inline dimensions guarantee the iOS pill shape even if Tailwind's
        // content scanner misses this file (lib/ was once outside content[]).
        style={{ width: 128, minWidth: 128, height: 40 }}
      >
        {/* gooey layer — the sliding neon bubble only; the filter melts it */}
        {/* into a liquid blob as it travels between the two segments       */}
        <div
          aria-hidden="true"
          className="absolute inset-0 w-full h-full pointer-events-none drop-shadow-[0_0_8px_rgba(0,255,157,0.4)]"
          style={{ filter: "url(#cyber-gooey)" }}
        >
          <span
            className={`absolute top-1 bottom-1 w-[calc(50%-4px)] bg-[#00ff9d] rounded-full transition-all duration-500 ease-in-out ${
              isArabic ? "left-[50%]" : "left-1"
            }`}
          />
        </div>

        {/* isolated text layer — dark on the blob when active, dim green when not */}
        <div className="relative z-10 flex w-full justify-between items-center px-4 pointer-events-none">
          <span
            className={`text-sm font-semibold font-mono tracking-wide transition-colors duration-300 ${
              !isArabic ? "text-[#080c10]" : "text-[#00ff9d]/40"
            }`}
          >
            EN
          </span>
          <span
            className={`text-sm font-bold transition-colors duration-300 ${
              isArabic ? "text-[#080c10]" : "text-[#00ff9d]/40"
            }`}
          >
            عربي
          </span>
        </div>
      </button>
    </div>
  );
}
