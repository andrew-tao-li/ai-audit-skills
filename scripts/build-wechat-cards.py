# -*- coding: utf-8 -*-
"""一次性：生成公众号用的 8 张卡片（手机适配版）并渲染成 PNG。

手机适配的硬约束：
  公众号图片按文章宽度显示（约 375px）。设计稿若 1080 宽 → 被压到 375 = 2.9 倍，
  14px 正文在手机上只剩 5px。所以这里：**画布宽 750**、**正文字号 >= 30**（750→375 = 2 倍）。
  每张只讲一件事，高度 1~1.5 屏，便于"一直往下划"。
"""
import subprocess, sys, re
from pathlib import Path

ROOT = Path("/Users/rockymary/ai-audit-skills/repo")
OUT = ROOT / "docs" / "wechat"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT.mkdir(parents=True, exist_ok=True)

CSS = """
*{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact}
html,body{width:750px;background:#eef2f8}
body{font:30px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#0f172a}
.card{width:750px;min-height:1000px;display:flex;flex-direction:column;background:#eef2f8}
.hero{background:radial-gradient(600px 300px at 85% 0%,rgba(56,189,248,.45),transparent 62%),
      linear-gradient(125deg,#070b18,#12203c 45%,#1d4ed8);color:#fff;padding:52px 46px 44px}
.kicker{font-size:24px;letter-spacing:6px;color:#7dd3fc;font-weight:800}
h1{font-size:76px;line-height:1.08;margin:16px 0 12px}
h1 em{font-style:normal;color:#7dd3fc}
.sub{font-size:32px;color:#c7d2fe;line-height:1.5}
.chips{display:flex;gap:12px;margin-top:30px;flex-wrap:wrap}
.chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:10px 22px;font-size:28px;color:#e0e7ff}
.body{padding:40px 46px 8px;flex:1}
h2{font-size:46px;margin:0 0 24px;display:flex;align-items:center;gap:14px}
h2 .bar{width:14px;height:44px;border-radius:7px;background:linear-gradient(#2563eb,#06b6d4)}
.blk{background:#fff;border-radius:24px;padding:24px 26px;margin-bottom:22px;border:1px solid #e4eaf4;
     box-shadow:0 8px 22px rgba(15,23,42,.06);border-left:14px solid var(--c,#2563eb)}
.blk .t{display:flex;align-items:baseline;gap:12px;margin-bottom:10px}
.blk .nm{font-size:38px;font-weight:800;color:var(--c,#2563eb)}
.blk .badge{font-size:24px;color:#64748b;background:#f1f5f9;border-radius:999px;padding:4px 16px;margin-left:auto;white-space:nowrap}
.blk .say{font-size:27px;color:#94a3b8;margin:-4px 0 12px}
.li{font-size:32px;color:#1e293b;margin:11px 0;padding-left:34px;position:relative}
.li::before{content:"";position:absolute;left:6px;top:15px;width:14px;height:14px;border-radius:50%;background:var(--c,#2563eb)}
.li b{font-weight:700}
.two{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.arrow{display:grid;place-items:center;font-size:56px;color:#94a3b8}
.flow{display:flex;align-items:stretch;gap:10px;margin:10px 0 26px}
.fbox{flex:1;border-radius:22px;padding:26px 20px;text-align:center;color:#fff}
.fbox b{display:block;font-size:36px;margin-bottom:6px}
.fbox span{font-size:26px;opacity:.9}
.f-in{background:linear-gradient(135deg,#2563eb,#0ea5e9)}
.f-mid{background:linear-gradient(135deg,#0f172a,#334155)}
.f-out{background:linear-gradient(135deg,#16a34a,#059669)}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:20px;padding:20px 24px;font-size:29px;color:#92400e;margin-top:6px}
.cols3{display:grid;grid-template-columns:1fr;gap:20px}
.g{border-radius:22px;padding:22px 24px;color:#fff}
.g h3{font-size:34px;margin-bottom:10px}
.g p{font-size:29px;color:rgba(255,255,255,.92);margin:8px 0;padding-left:26px;position:relative}
.g p::before{content:"•";position:absolute;left:4px}
.g.edge{background:linear-gradient(135deg,#b91c1c,#ef4444)}
.g.risk{background:linear-gradient(135deg,#b45309,#f59e0b)}
.g.safe{background:linear-gradient(135deg,#047857,#10b981)}
.steps{counter-reset:s}
.step{display:flex;gap:20px;align-items:flex-start;background:#fff;border-radius:22px;padding:24px 26px;margin-bottom:20px;
      border:1px solid #e4eaf4;box-shadow:0 8px 22px rgba(15,23,42,.06)}
.step .n{flex:0 0 66px;height:66px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;
      display:grid;place-items:center;font-size:34px;font-weight:800}
.step .txt{font-size:32px}
.step .txt b{display:block;font-size:34px;margin-bottom:4px}
.foot{margin-top:auto;padding:26px 46px 34px;display:flex;align-items:center;justify-content:space-between;
      font-size:26px;color:#64748b}
.dots{display:flex;gap:9px}
.dots i{width:14px;height:14px;border-radius:50%;background:#cbd5e1;display:inline-block}
.dots i.on{background:#2563eb;width:34px;border-radius:999px}
.cta{background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#fff;border-radius:24px;padding:30px 32px;text-align:center;margin-top:8px}
.cta b{font-size:40px;display:block;margin-bottom:8px;color:#7dd3fc}
.cta span{font-size:30px;color:#dbeafe}
"""

def page(i, total, inner, title="费用审计技能"):
    dots = "".join('<i class="%s"></i>' % ("on" if k == i else "") for k in range(1, total + 1))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="card">{inner}
<div class="foot"><div>{title} · 第 {i}/{total} 张</div><div class="dots">{dots}</div></div>
</div>
<script>window.addEventListener('load',function(){{document.documentElement.setAttribute('data-h',document.body.scrollHeight)}});</script>
</body></html>"""

TOTAL = 8

# 1 封面
c1 = f"""
<div class="hero">
  <div class="kicker">AUDIT AI · 一图看懂</div>
  <h1>费用审计技能<em>。</em></h1>
  <div class="sub">把一整本报销台账，<br>变成<b>可复核的线索</b>。</div>
  <div class="chips"><span class="chip">43 条规则</span><span class="chip">8 大域</span><span class="chip">0 次联网</span></div>
</div>
<div class="body" style="display:grid;align-content:center">
  <div style="text-align:center;font-size:36px;color:#64748b;line-height:1.8">
    机器负责<b style="color:#0f172a">全量找线索</b><br>人负责<b style="color:#0f172a">定性</b><br><br>
    <span style="font-size:30px;color:#94a3b8">↓ 往下滑，8 张图看懂</span>
  </div>
</div>"""

# 2 它是什么
c2 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">01</div><h1 style="font-size:54px">它做什么</h1></div>
<div class="body">
  <div class="flow">
    <div class="fbox f-in"><b>一张台账</b><span>费用 / 报销明细</span></div>
    <div class="arrow">→</div>
    <div class="fbox f-mid"><b>43 条规则</b><span>全量扫描</span></div>
    <div class="arrow">→</div>
    <div class="fbox f-out"><b>一页线索</b><span>每条都能回源</span></div>
  </div>
  <div class="blk" style="--c:#2563eb;border-left-color:#2563eb">
    <div class="li" style="--c:#2563eb">它只做「<b>数据之间对得上</b>」的核对</div>
    <div class="li" style="--c:#dc2626">不下结论、不做认定 —— <b>异常 ≠ 舞弊</b></div>
  </div>
</div>"""

# 3 给它什么
c3 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">02</div><h1 style="font-size:54px">给它什么</h1></div>
<div class="body">
  <div class="blk" style="--c:#16a34a;border-left-color:#16a34a">
    <div class="t"><div class="nm">必须有</div><div class="badge">1 样</div></div>
    <div class="li" style="--c:#16a34a"><b>1 张台账</b>：CSV / Excel（费用、报销、发票明细都行）</div>
  </div>
  <div class="blk" style="--c:#d97706;border-left-color:#d97706">
    <div class="t"><div class="nm">可选</div><div class="badge">给了才生效</div></div>
    <div class="li" style="--c:#d97706"><b>制度</b>：限额、审批阈值、节假日</div>
    <div class="li" style="--c:#d97706"><b>辅助数据</b>：出差申请 / 打卡 / 航班核验 / 支付流水 / 市场价 / 运单</div>
  </div>
  <div class="note">不给可选项也能跑；给了，才多出对应能力。</div>
</div>"""

# 4 能查出什么（一）
def domain(color, letter, name, count, say, rules):
    li = "".join('<div class="li" style="--c:%s">%s</div>' % (color, r) for r in rules)
    return (f'<div class="blk" style="--c:{color};border-left-color:{color}">'
            f'<div class="t"><div class="nm">{letter} · {name}</div><div class="badge">{count}</div></div>'
            f'<div class="say">{say}</div>{li}</div>')

c4 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">03</div><h1 style="font-size:54px">能查出什么（一）</h1></div>
<div class="body">
  {domain("#2563eb","A","重复与复用","9 条","同一笔被报两次", ["发票号重复 · 同人同日同额","发票跨人复用 · 同一凭证多人各报","高频小额 · 撤回重提加码"])}
  {domain("#0891b2","B","制度与阈值","7 条","比制度、比审批权限", ["超制度上限 · 拆单报销","跨商户拆单 · 超适用差标","大额低层级审批 · 单价高于市场价"])}
  {domain("#7c3aed","C","时序与日期","8 条","时间对不上", ["提交早于消费 · 未来日期","跨期入账 · 日期与周几不符"])}
  {domain("#db2777","D","行为与集中度","4 条","谁在自批、钱流去哪", ["自审自批（含多人审批列表）","商户集中度 · 时空冲突"])}
</div>"""

c5 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">04</div><h1 style="font-size:54px">能查出什么（二）</h1></div>
<div class="body">
  {domain("#ea580c","E","统计离群","1 条","同类里相对偏高", ["异常高额（相对，不是绝对高）"])}
  {domain("#16a34a","F","凭证 / 票据真实性","9 条","票本身有没有破绽", ["凭证要素不全 · 发票连号","发票格式异常 · 订座号同日矛盾"])}
  {domain("#ca8a04","G","外部核验","6 条 · 需外部数据","拿外部事实来比对", ["行程与航班记录不符（查不到 ≠ 虚构）","替票：开票方 ≠ 实际收款方 · 运单勾稽"])}
  {domain("#0d9488","H","差旅交叉","3 条 · 需辅助数据","台账 × 申请 × 打卡", ["差旅无出差申请 · 打卡城市不符"])}
</div>"""

# 6 出料
c6 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">05</div><h1 style="font-size:54px">给你什么</h1></div>
<div class="body">
  <div class="blk" style="--c:#7c3aed;border-left-color:#7c3aed">
    <div class="li" style="--c:#7c3aed"><b>dashboard.html</b> —— 一页全景图，经理先看这个</div>
    <div class="li" style="--c:#7c3aed"><b>summary.md</b> —— 完整结论 + 建议复核顺序</div>
    <div class="li" style="--c:#7c3aed"><b>findings + evidence</b> —— 每条线索都能追回原始行</div>
  </div>
  <div class="note">每条线索都带<b>行级证据</b>与哈希，可复核、可复现。</div>
</div>"""

# 7 护栏
c7 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">06</div><h1 style="font-size:54px">用之前要知道</h1></div>
<div class="body">
  <div class="cols3">
    <div class="g edge"><h3>🚧 边界</h3><p>不判断业务实质（费用是否真发生）</p><p>不做舞弊 / 拒付认定</p><p>不验发票真伪、不连银行流水</p></div>
    <div class="g risk"><h3>⚠️ 风险</h3><p>异常 ≠ 舞弊；未发现问题 ≠ 没有问题</p><p>会有漏报和误报，只做优先级排序</p><p>最终定性必须由有资质的人做</p></div>
    <div class="g safe"><h3>🔒 安全与隐私</h3><p>全程离线：不联网、不上传、无外部服务</p><p>不内置密钥，不调任何大模型 API</p><p>只读输入 · 不静默丢弃 · 可复现</p></div>
  </div>
</div>"""

# 8 怎么用 + 互动
c8 = f"""
<div class="hero" style="padding:40px 46px 34px"><div class="kicker">07</div><h1 style="font-size:54px">怎么用</h1></div>
<div class="body">
  <div class="steps">
    <div class="step"><div class="n">1</div><div class="txt"><b>给它一张台账</b>什么都不配也能跑</div></div>
    <div class="step"><div class="n">2</div><div class="txt"><b>看 dashboard</b>先查高危线索，再逐条核实</div></div>
    <div class="step"><div class="n">3</div><div class="txt"><b>需要更深</b>再补辅助数据（出差/打卡/运单…）</div></div>
  </div>
  <div class="cta"><b>想要试用？</b><span>在公众号留言「<b>费用审计</b>」<br>获取安装方式</span></div>
</div>"""

pages = [c1, c2, c3, c4, c5, c6, c7, c8]
names = ["01-cover","02-what-it-does","03-inputs","04-domains-1","05-domains-2","06-outputs","07-guardrails","08-how-to-use"]

for idx, (inner, name) in enumerate(zip(pages, names), start=1):
    html = OUT / ("%s.html" % name)
    html.write_text(page(idx, TOTAL, inner), encoding="utf-8")
    dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                          "--virtual-time-budget=2500", "--dump-dom", "file://%s" % html],
                         capture_output=True, text=True).stdout
    m = re.search(r'data-h="(\d+)"', dom)
    h = int(m.group(1)) if m else 1100
    h = max(h, 1000)
    png = OUT / ("%s.png" % name)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=750,%d" % h,
                    "--screenshot=%s" % png, "file://%s" % html],
                   capture_output=True, text=True)
    print("  %-22s %4dpx → %s" % (name, h, png.name))
print("done:", OUT)
