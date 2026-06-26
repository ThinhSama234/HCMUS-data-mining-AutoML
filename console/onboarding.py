"""First-visit onboarding — a one-time welcome dialog with a looping 4-step demo.

Shown once per session (gated on `st.session_state`); "Không hiện lại" + "Bắt đầu" dismiss it.
The looping demo is a self-contained HTML/CSS/JS snippet rendered in an iframe via
`st.components.v1.html` (Streamlit has no native video; this mock loops with no media files).
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

_SEEN = "_onboarded"

# Looping demo: 4 frames mirroring the real pages, auto-advancing + a click ripple on each CTA.
_DEMO_HTML = """
<style>
  :root{--teal:#0C6E6A;--teal2:#0E2A28;--amber:#C9620A;--ink:#14201F;--muted:#5C6B69;
        --line:#DCE3E1;--ground:#F4F6F5;--ok:#2E7D5B;--fail:#B23A48;
        --mono:ui-monospace,Menlo,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
  *{box-sizing:border-box} html,body{margin:0}
  body{font-family:var(--sans);color:var(--ink);background:transparent}
  .stage{border:1px solid var(--line);border-radius:11px;overflow:hidden;background:var(--ground)}
  .demobar{display:flex;align-items:center;gap:6px;padding:7px 11px;border-bottom:1px solid var(--line);background:#fff}
  .d3{width:9px;height:9px;border-radius:50%;background:#e0e4e3}
  .demobar .lbl{margin-left:auto;font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--muted);display:flex;align-items:center;gap:6px}
  .live{width:7px;height:7px;border-radius:50%;background:var(--teal);animation:pulse 2s ease-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 #0c6e6a66}70%{box-shadow:0 0 0 6px #0c6e6a00}100%{box-shadow:0 0 0 0 #0c6e6a00}}
  .frames{position:relative;height:228px}
  .frame{position:absolute;inset:0;display:flex;opacity:0;transition:opacity .5s ease}
  .frame.on{opacity:1}
  .rail{width:96px;background:var(--teal2);color:#cfe0dd;padding:12px 9px;flex:none;font-size:10px}
  .rail .grp{font-family:var(--mono);font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;color:#cfe0dd99;margin:9px 2px 4px}
  .rail .it{padding:4px 7px;border-radius:6px;margin:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .rail .it.act{background:var(--teal);color:#fff;font-weight:600}
  .screen{flex:1;padding:14px 16px;background:var(--ground)}
  .screen .t{font-size:13.5px;font-weight:700;margin-bottom:3px}
  .screen .sub{font-size:11px;color:var(--muted);margin-bottom:11px}
  .drop{border:1.5px dashed var(--teal);border-radius:9px;padding:13px;text-align:center;color:var(--teal);font-size:11.5px;background:#0c6e6a0a}
  .tbl{margin-top:9px;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .tbl .tr{display:flex;gap:8px;padding:6px 10px;border-bottom:1px solid var(--line);font-size:10px;color:var(--muted)}
  .tbl .tr:last-child{border:0}.tbl .tr span{flex:1}
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
  .mcard{background:#fff;border:1px solid var(--line);border-radius:9px;padding:9px}
  .mcard .nm{font-size:11px;font-weight:600;margin-bottom:5px}
  .pill{font-family:var(--mono);font-size:9px;font-weight:600;padding:2px 7px;border-radius:20px}
  .pill.ok{background:#2e7d5b1a;color:var(--ok)}.pill.q{background:#5c6b6914;color:var(--muted)}
  .chips{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}.chip{background:var(--teal);color:#fff;font-size:10px;border-radius:7px;padding:3px 9px}
  .sel{background:#fff;border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:11px;display:flex;justify-content:space-between}
  .bars{display:flex;flex-direction:column;gap:7px;margin-top:6px}.bar{display:flex;align-items:center;gap:8px;font-size:11px}.bar i{font-style:normal}
  .track{height:14px;border-radius:4px;background:var(--teal)}
  .cta{margin-top:11px;display:inline-block;background:var(--amber);color:#fff;font-size:11.5px;font-weight:600;padding:7px 14px;border-radius:8px;position:relative}
  .frame.on .cta::after{content:"";position:absolute;inset:-6px;border-radius:12px;border:2px solid var(--amber);animation:click 1.6s ease-out .5s infinite}
  @keyframes click{0%{transform:scale(.7);opacity:0}30%{opacity:.8}100%{transform:scale(1.25);opacity:0}}
  .cap{padding:12px 4px 2px}.cap .step{font-family:var(--mono);font-size:11px;color:var(--amber);font-weight:600}
  .cap .ct{font-size:14px;font-weight:600;margin:.15rem 0}.cap .cd{font-size:12.5px;color:var(--muted);line-height:1.45}
  .dots{display:flex;gap:7px;justify-content:center;padding:8px 0 2px}
  .dots button{width:26px;height:5px;border-radius:3px;border:0;background:#d4dbd9;cursor:pointer;padding:0;transition:background .3s}
  .dots button[aria-current="true"]{background:var(--teal)}.dots button:focus-visible{outline:2px solid var(--amber);outline-offset:3px}
  @media (prefers-reduced-motion:reduce){.frame{transition:none}.live,.frame.on .cta::after{animation:none}}
</style>
<div class="stage">
  <div class="demobar"><span class="d3"></span><span class="d3"></span><span class="d3"></span>
    <span class="lbl"><span class="live"></span>DEMO · TỰ LẶP</span></div>
  <div class="frames">
    <div class="frame on" data-i="0"><div class="rail"><div class="grp">Build</div>
      <div class="it act">🗂 Datasets</div><div class="it">🧩 Methods</div><div class="it">🚀 Training</div></div>
      <div class="screen"><div class="t">Datasets</div><div class="sub">Tải dữ liệu vào catalog</div>
        <div class="drop">⬆ Kéo–thả CSV · hoặc “Browse files”</div>
        <div class="tbl"><div class="tr"><span>loan_binary</span><span>upload</span><span>binary</span></div>
          <div class="tr"><span>iris</span><span>openml</span><span>multiclass</span></div></div>
        <span class="cta">Add from OpenML</span></div></div>
    <div class="frame" data-i="1"><div class="rail"><div class="grp">Build</div>
      <div class="it">🗂 Datasets</div><div class="it act">🧩 Methods</div><div class="it">🚀 Training</div></div>
      <div class="screen"><div class="t">Methods</div><div class="sub">Tích hợp framework (kéo image AMLB)</div>
        <div class="cards"><div class="mcard"><div class="nm">flaml</div><span class="pill ok">integrated</span></div>
          <div class="mcard"><div class="nm">gama</div><span class="pill q">available</span></div>
          <div class="mcard"><div class="nm">autosklearn</div><span class="pill ok">integrated</span></div></div>
        <span class="cta">Integrate</span></div></div>
    <div class="frame" data-i="2"><div class="rail"><div class="grp">Build</div>
      <div class="it">🗂 Datasets</div><div class="it">🧩 Methods</div><div class="it act">🚀 Training</div></div>
      <div class="screen"><div class="t">Training</div><div class="sub">Chọn framework + dataset → chạy thật</div>
        <div class="sel">flaml <span>▾</span></div>
        <div class="chips"><span class="chip">credit-g</span><span class="chip">vehicle</span><span class="chip">phoneme</span></div>
        <span class="cta">🚀 Launch on 3 dataset(s)</span></div></div>
    <div class="frame" data-i="3"><div class="rail"><div class="grp">Analyze</div>
      <div class="it act">📊 Evaluation</div><div class="it">🗂 Datasets</div><div class="it">🧩 Methods</div></div>
      <div class="screen"><div class="t">Evaluation</div><div class="sub">Bảng xếp hạng &amp; biểu đồ</div>
        <div class="bars"><div class="bar"><i>🥇 flaml</i><div class="track" style="width:62%"></div></div>
          <div class="bar"><i>🥈 RandomForest</i><div class="track" style="width:46%;opacity:.8"></div></div>
          <div class="bar"><i>🥉 constantpredictor</i><div class="track" style="width:20%;opacity:.6"></div></div></div></div></div>
  </div>
</div>
<div class="cap" id="cap" aria-live="polite"></div>
<div class="dots" id="dots" role="tablist" aria-label="Các bước"></div>
<script>
  const STEPS=[
    {s:"Bước 1 / 4 · Datasets",t:"Thêm dữ liệu",d:"Upload CSV của bạn, hoặc Add from OpenML bằng task id — lưu vào object store + catalog."},
    {s:"Bước 2 / 4 · Methods",t:"Tích hợp framework",d:"Bấm Integrate để kéo Docker image AMLB về; trạng thái chuyển integrated khi sẵn sàng."},
    {s:"Bước 3 / 4 · Training",t:"Chạy benchmark",d:"Chọn framework đã integrated + dataset → Launch. Job chạy Docker thật, theo dõi ở bảng Jobs."},
    {s:"Bước 4 / 4 · Evaluation",t:"Xem kết quả",d:"Bảng xếp hạng 🥇🥈🥉, biểu đồ Pareto và phân tích theo đặc trưng — cập nhật khi job xong."},
  ];
  const frames=[...document.querySelectorAll('.frame')],cap=document.getElementById('cap'),db=document.getElementById('dots');
  let i=0,timer=null;const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  STEPS.forEach((_,k)=>{const b=document.createElement('button');b.setAttribute('role','tab');b.onclick=()=>{show(k);rearm()};db.appendChild(b)});
  const dots=[...db.children];
  function show(k){i=k;frames.forEach((f,n)=>f.classList.toggle('on',n===k));dots.forEach((d,n)=>d.setAttribute('aria-current',n===k));
    cap.innerHTML='<div class="step">'+STEPS[k].s+'</div><div class="ct">'+STEPS[k].t+'</div><div class="cd">'+STEPS[k].d+'</div>';}
  function rearm(){clearInterval(timer);if(!reduce)timer=setInterval(()=>show((i+1)%STEPS.length),4000);}
  document.querySelector('.stage').addEventListener('mouseenter',()=>clearInterval(timer));
  document.querySelector('.stage').addEventListener('mouseleave',rearm);
  show(0);rearm();
</script>
"""


def maybe_show():
    """Open the welcome dialog once per session (call from the app entrypoint)."""
    if st.session_state.get(_SEEN):
        return

    @st.dialog("👋 Chào mừng đến AutoML Bench Console", width="large")
    def _welcome():
        st.markdown("**4 bước để có kết quả benchmark** — thêm dữ liệu → tích hợp framework "
                    "→ chạy → xem kết quả. Demo dưới đây tự lặp.")
        components.html(_DEMO_HTML, height=360, scrolling=False)
        c1, c2 = st.columns([3, 1])
        c1.caption("Mẹo: rê chuột vào demo để tạm dừng · bấm vạch để nhảy bước.")
        if c2.button("Bắt đầu →", type="primary", use_container_width=True):
            st.session_state[_SEEN] = True
            st.rerun()

    st.session_state[_SEEN] = True   # mark shown so it won't reopen on later reruns this session
    _welcome()
