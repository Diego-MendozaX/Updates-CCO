(() => {
  "use strict";
  const D = JSON.parse(document.getElementById("cco-data").textContent),
    $ = (id) => document.getElementById(id);
  const COLORS = {
    Hidráulica: "#3599B8",
    Térmica: "#E80870",
    Eólica: "#682888",
    Solar: "#F8A018",
    "Otras RER": "#8D8C8F",
    "Sin clasificación": "#C4B4CE",
  };
  const PAL = [
    "#A62E78",
    "#682888",
    "#3599B8",
    "#E86820",
    "#F8A018",
    "#9B4FA6",
    "#4AC5BB",
    "#C82828",
    "#8D8C8F",
    "#B687AC",
    "#28738A",
    "#FDAB89",
    "#7F898A",
    "#B59525",
    "#BB4A4A",
    "#6A9FB0",
    "#168980",
    "#5F6B6D",
    "#FB8281",
    "#7B4F71",
  ];
  const NAV = [
    [
      "executive",
      "Resumen ejecutivo",
      "dashboard",
      "Visión integrada del despacho, la demanda y el impacto de cada emisión.",
    ],
    [
      "inkia",
      "Despacho INKIA",
      "bolt",
      "Kallpa, Orazul, Kondu y Joya Solar. Cada central, en contexto.",
    ],
    [
      "hydro",
      "Hidrología y embalses",
      "water",
      "Caudales, utilización hidráulica y evolución diaria de los embalses.",
    ],
    [
      "thermal",
      "Otras empresas · 1/2",
      "bars",
      "Despacho convencional, potencia de referencia y energía por central.",
    ],
    [
      "renewable",
      "Otras empresas · 2/2",
      "wind",
      "Generación eólica, solar y otras renovables del sistema.",
    ],
    [
      "reserves",
      "RPF / RSF",
      "pulse",
      "Reserva primaria y secundaria de frecuencia, con sus fuentes y vigencias.",
    ],
    [
      "maintenance",
      "Mantenimientos",
      "calendar",
      "Intervenciones previstas y restricciones de la jornada.",
    ],
    [
      "electrical",
      "Análisis eléctrico",
      "network",
      "Cargabilidades publicadas y flujos previstos en los enlaces del SEIN.",
    ],
    [
      "notes",
      "Apuntes operativos",
      "note",
      "Decisiones, observaciones y seguimiento de la operación.",
    ],
    [
      "changes",
      "Variaciones",
      "compare",
      "El cambio entre dos emisiones, hasta el equipo y el intervalo.",
    ],
    [
      "catalog",
      "Catálogos y alertas",
      "pulse",
      "Matrices, nuevas unidades, cambios de nombre y revisión de parámetros técnicos.",
    ],
    [
      "archive",
      "Archivo de programas",
      "folder",
      "Cada original, cada revisión y cada anexo en un solo lugar.",
    ],
  ];
  const ICONS = {
    dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
    bolt: "m13 2-9 12h7l-1 8 10-13h-7z",
    water: "M12 3C9 8 5 10 5 15a7 7 0 0 0 14 0c0-5-4-7-7-12z",
    bars: "M5 20V10M12 20V4M19 20V14M2 20h20",
    wind: "M3 8h12a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7a3 3 0 1 1-3 3",
    pulse: "M2 12h5l3-8 4 16 3-8h5",
    calendar: "M4 5h16v16H4zM4 10h16M8 2v6M16 2v6",
    network: "M8 3h8v5H8zM2 16h7v5H2zM15 16h7v5h-7zM12 8v4M5 16v-4h14v4",
    note: "M5 3h14v18H5zM8 8h8M8 12h8M8 16h5",
    compare: "M3 7h17l-4-4M21 17H4l4 4",
    folder: "M3 5h7l2 3h9v13H3z",
  };
  const h = (x) =>
    String(x ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const norm = (s) =>
    String(s || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "");
  const fmt = (n, d = 1) =>
    n == null || !Number.isFinite(n)
      ? "—"
      : new Intl.NumberFormat("es-PE", {
          maximumFractionDigits: d,
          minimumFractionDigits: d,
        }).format(Math.abs(n) < Math.pow(10, -d) / 2 ? 0 : n);
  const sign = (n, d = 1) => (n == null ? "—" : (n > 0 ? "+" : "") + fmt(n, d));
  const title = (c) => (c === "PDO" ? "PDO" : "REP " + c);
  const stamp = (s) =>
    s
      ? new Date(s).toLocaleString("es-PE", {
          timeZone: "America/Lima",
          hour12: false,
        })
      : "Sin consulta";
  const numberCode = (c) =>
    c === "PDO" ? 0 : [...c].reduce((n, x) => n * 26 + x.charCodeAt(0) - 64, 0);
  const current = D.versions
    .filter((v) => v.current)
    .sort(
      (a, b) =>
        a.day.localeCompare(b.day) || numberCode(a.code) - numberCode(b.code),
    );
  const days = [
    ...new Set([...current.map((v) => v.day), ...D.runs.map((r) => r.day)]),
  ]
    .sort()
    .reverse();
  const hash = new URLSearchParams(location.hash.slice(1));
  const S = {
    day: days.includes(hash.get("day")) ? hash.get("day") : days[0] || "",
    code: hash.get("code") || "",
    page: NAV.some((n) => n[0] === hash.get("page"))
      ? hash.get("page")
      : "executive",
    follow: hash.get("follow") !== "0",
    scope: ["all", "inkia", "others"].includes(hash.get("scope"))
      ? hash.get("scope")
      : "all",
    company: hash.get("company") || "",
    plant: hash.get("plant") || "",
    technology: hash.get("technology") || "",
    period: ["common", "day", "morning", "daytime", "evening"].includes(
      hash.get("period"),
    )
      ? hash.get("period")
      : "common",
    reservoir: hash.get("reservoir") || "",
    urs: hash.get("urs") || "",
    eventView: "maintenance",
    eventCategory: "",
    search: "",
    threshold: 100,
    changeKind: "generation",
    series: hash.get("series") || "",
    electricalPage: "",
    tables: {},
    revisions: false,
    hydroFlowScope: hash.get("hydroFlowScope") || "inkia",
    reservoirScope: hash.get("reservoirScope") || "all",
    reservoirCompany: hash.get("reservoirCompany") || "",
    catalogTab: hash.get("catalogTab") || "alerts",
  };
  let active = null,
    previous = null,
    charts = [],
    exportRows = [],
    timer,
    debounce;
  Chart.defaults.font.family = "Segoe UI,system-ui,sans-serif";
  Chart.defaults.font.size = 10;
  Chart.defaults.color = "#67526F";
  Chart.defaults.borderColor = "#F0EAF4";
  Chart.defaults.animation = false;
  function badge(t, type = "info") {
    return `<span class="badge ${type}">${h(t)}</span>`;
  }
  function icon(name) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[name] || ICONS.dashboard}"/></svg>`;
  }
  function persist() {
    const p = new URLSearchParams({
      day: S.day,
      code: S.code,
      page: S.page,
      follow: S.follow ? "1" : "0",
      scope: S.scope,
      company: S.company,
      plant: S.plant,
      technology: S.technology,
      period: S.period,
      reservoir: S.reservoir,
      urs: S.urs,
      series: S.series,
      hydroFlowScope: S.hydroFlowScope,
      reservoirScope: S.reservoirScope,
      reservoirCompany: S.reservoirCompany,
      catalogTab: S.catalogTab,
    });
    try {
      history.replaceState(null, "", "#" + p);
    } catch (_) {}
  }
  function toast(message) {
    $("toast").textContent = message;
    $("toast").classList.remove("hidden");
    clearTimeout(timer);
    timer = setTimeout(() => $("toast").classList.add("hidden"), 4000);
  }
  function setOptions(id, values, empty) {
    const e = $(id),
      old = S[id];
    e.replaceChildren();
    const option = (v, t) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = t;
      return o;
    };
    if (empty) e.append(option("", empty));
    for (const x of values) e.append(option(x, x));
    if (!values.includes(old)) S[id] = "";
    e.value = S[id];
  }
  function scoped(a, scope = S.scope) {
    return (
      (scope === "all" || (scope === "inkia" ? a.inkia : !a.inkia)) &&
      (!S.company || a.company === S.company) &&
      (!S.plant || a.plant === S.plant) &&
      (!S.technology || a.technology === S.technology)
    );
  }
  function gens(v = active, mode = "filtered") {
    return (v?.series || []).filter(
      (a) => a.generation && (mode === "all" || scoped(a)),
    );
  }
  function viewAssets(v = active) {
    let a = gens(v);
    if (S.page === "inkia") a = a.filter((a) => a.inkia);
    if (S.page === "thermal")
      a = a.filter(
        (a) => !a.inkia && ["Térmica", "Hidráulica"].includes(a.category),
      );
    if (S.page === "renewable")
      a = a.filter(
        (a) =>
          !a.inkia && ["Solar", "Eólica", "Otras RER"].includes(a.category),
      );
    return a;
  }
  function idx() {
    let start = 0,
      end = 48;
    const first = (v) => v?.series[0]?.first_interval_index || 0;
    if (S.period === "common") start = Math.max(first(active), first(previous));
    else if (S.period === "morning") end = 16;
    else if (S.period === "daytime") {
      start = 16;
      end = 32;
    } else if (S.period === "evening") start = 32;
    return Array.from({ length: end - start }, (_, i) => i + start);
  }
  function values(a) {
    return idx().map((i) => a?.values[i] ?? null);
  }
  function sumAt(assets, i) {
    const n = assets
      .map((a) => a.values[i])
      .filter((n) => n != null && Number.isFinite(n));
    return n.length ? n.reduce((a, b) => a + b, 0) : null;
  }
  function aggregate(assets) {
    return idx().map((i) => sumAt(assets, i));
  }
  function total(assets) {
    const xs = aggregate(assets).filter((n) => n != null);
    return xs.length ? (xs.reduce((a, b) => a + b, 0) * 0.5) / 1000 : null;
  }
  function avg(xs) {
    const n = xs.filter((n) => n != null && Number.isFinite(n));
    return n.length ? n.reduce((a, b) => a + b, 0) / n.length : null;
  }
  function max(xs) {
    const n = xs.filter((n) => n != null && Number.isFinite(n));
    return n.length ? Math.max(...n) : null;
  }
  function subtract(a, b) {
    return a == null || b == null ? null : a - b;
  }
  function sourceSeries(role, v = active) {
    return v?.series.find((a) => a.role === role);
  }
  function reportedGeneration(v = active) {
    return S.scope === "all" && !S.company && !S.plant && !S.technology
      ? values(sourceSeries("generation_total", v))
      : aggregate(gens(v));
  }
  function energyValues(xs) {
    const n = xs.filter((x) => x != null);
    return n.length ? (n.reduce((a, b) => a + b, 0) * 0.5) / 1000 : null;
  }
  function group(assets, key) {
    const map = new Map();
    for (const a of assets) {
      const k = a[key] || "Sin clasificación";
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(a);
    }
    return [...map];
  }
  function capacity(assets) {
    if (
      !assets.length ||
      assets.some(
        (a) =>
          !(a.capacity > 0) ||
          a.commercial_status === "fuera_de_operacion_comercial",
      )
    )
      return null;
    const map = new Map();
    for (const a of assets)
      if (a.capacity > 0)
        map.set(a.plant, Math.max(map.get(a.plant) || 0, a.capacity));
    return map.size ? [...map.values()].reduce((a, b) => a + b, 0) : null;
  }
  function extra() {
    return (
      D.supplements?.[S.day] || {
        daily: {},
        reserves: {},
        files: [],
        errors: [],
      }
    );
  }
  function daily(kind) {
    return extra().daily?.[kind];
  }
  function rsf() {
    const x = extra();
    return x.reserves?.[S.code] || x.reserves?.PDO || null;
  }
  function missing(
    titleText,
    message = "Este anexo no está disponible para la fecha elegida. Ejecuta el script de actualización para consultar las fuentes publicadas.",
  ) {
    return `<div class="missing"><span class="empty-symbol">◇</span><strong>${h(titleText)}</strong><span>${h(message)}</span></div>`;
  }
  function kpi(
    label,
    value,
    unit,
    old = null,
    accent = "#A62E78",
    caption = "Ventana seleccionada",
    symbol = "↗",
    digits = 1,
  ) {
    const delta = subtract(value, old);
    return `<article class="kpi" style="--accent:${accent};--accent-bg:${accent}0D"><div class="kpi-title">${h(label)}<span class="kpi-symbol">${icon(symbol === "ϟ" ? "bolt" : symbol === "▥" ? "bars" : symbol === "⇄" ? "compare" : "pulse")}</span></div><div class="kpi-value">${fmt(value, digits)}<small>${h(unit)}</small></div><div class="kpi-sub">${old != null ? `<span class="change ${delta < 0 ? "down" : Math.abs(delta || 0) < 0.00001 ? "no-change" : ""}">${sign(delta, digits)} ${h(unit)}</span><span>vs ${h(title(previous?.code || "PDO"))}</span>` : h(caption)}</div></article>`;
  }
  function panel(id, label, subtitle = "", note = "", size = "") {
    return `<section class="panel" data-chart="${id}"><div class="panel-head"><div><h2>${h(label)}</h2><p>${h(subtitle)}</p></div><span class="head-icon">${icon("compare")}</span></div><div class="chart-box ${size}"><canvas id="${id}" role="img" aria-label="${h(label)}"></canvas></div>${note ? `<div class="panel-note"><span>${h(note)}</span></div>` : ""}</section>`;
  }
  function sourceBar(kinds, label = "Anexos de la jornada") {
    const ds = kinds.map((k) => daily(k)).filter(Boolean);
    return `<div class="source-bar"><span><strong>${h(label)}</strong> · ${h(S.day.split("-").reverse().join("/"))} · información diaria PDO/PDI${S.code !== "PDO" ? `; el despacho seleccionado es ${h(title(S.code))}` : ""}.</span>${ds.length ? `<a href="${h(encodeURI(ds[0].source.file))}" download>Descargar fuente ↗</a>` : "<span>Fuente pendiente</span>"}</div>`;
  }
  function table(
    headers,
    rows,
    {
      limit = 20,
      id = "table",
      empty = "Sin registros para esta selección.",
    } = {},
  ) {
    const pages = Math.max(1, Math.ceil(rows.length / limit));
    const page = Math.max(1, Math.min(S.tables[id] || 1, pages));
    S.tables[id] = page;
    const start = (page - 1) * limit,
      body = rows
        .slice(start, start + limit)
        .map(
          (row) =>
            `<tr>${row.map((c) => `<td>${typeof c === "object" && c !== null ? c.html : h(c)}</td>`).join("")}</tr>`,
        )
        .join("");
    return `<div class="table-scroll"><table id="${id}"><thead><tr>${headers.map((x) => `<th>${h(x)}</th>`).join("")}</tr></thead><tbody>${body || `<tr><td colspan="${headers.length}" class="missing" style="height:120px">${h(empty)}</td></tr>`}</tbody></table></div><div class="table-footer"><span>${rows.length ? `${start + 1}–${Math.min(start + limit, rows.length)} de ${rows.length}` : "0 registros"}</span><div class="pagination"><button data-action="prev" data-table="${id}" ${page <= 1 ? "disabled" : ""}>Anterior</button><span>${page} / ${pages}</span><button data-action="next" data-table="${id}" ${page >= pages ? "disabled" : ""}>Siguiente</button></div></div>`;
  }
  function opts(map, unit = "MW", extras = {}) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      layout: { padding: { left: 0, right: 7, bottom: 3 } },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            boxWidth: 7,
            boxHeight: 7,
            usePointStyle: true,
            padding: 14,
            font: { size: 9 },
          },
          maxHeight: 70,
        },
        tooltip: {
          backgroundColor: "#fff",
          titleColor: "#542460",
          bodyColor: "#67526F",
          borderColor: "#e4d5eb",
          borderWidth: 1,
          padding: 12,
          displayColors: true,
          callbacks: {
            label: (c) =>
              `${c.dataset.label}: ${fmt(c.parsed.y ?? c.parsed.x, 2)} ${c.dataset.unit || unit}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: "#73617D",
            font: { size: 9 },
            maxTicksLimit: 9,
            maxRotation: 0,
          },
        },
        y: {
          beginAtZero: true,
          grid: { color: "#F2EBF6", drawTicks: false },
          border: { display: false },
          ticks: { color: "#73617D", font: { size: 9 }, maxTicksLimit: 6 },
          title: {
            display: true,
            text: unit,
            color: "#73617D",
            font: { size: 9 },
          },
        },
      },
      ...extras,
    };
  }
  function chart(id, type, labels, datasets, unit = "MW", override = {}) {
    const canvas = $(id);
    if (!canvas) return;
    const has = datasets.some((d) =>
      d.data?.some((n) => typeof n === "number" && Number.isFinite(n)),
    );
    if (!has) {
      canvas.parentElement.outerHTML = missing(
        "Sin valores publicados",
        "No se calculan ceros ni se completan horas anteriores a la vigencia del programa.",
      );
      return;
    }
    const options = opts(null, unit);
    if (override.scales) Object.assign(options.scales, override.scales);
    if (override.plugins) Object.assign(options.plugins, override.plugins);
    if (override.indexAxis) options.indexAxis = override.indexAxis;
    charts.push(
      new Chart(canvas, { type, data: { labels, datasets }, options }),
    );
  }
  function line(label, data, color = "#A62E78", old = false) {
    return {
      type: "line",
      label,
      data,
      borderColor: color,
      backgroundColor: color + "12",
      borderWidth: old ? 1.7 : 2.2,
      borderDash: old ? [5, 4] : [],
      stack: label,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.18,
      spanGaps: false,
      fill: false,
      order: 0,
    };
  }
  function stacked(id, assets, { comparison = false, demand = false } = {}) {
    const sets = group(assets, "category").map(([c, a]) => ({
      type: "bar",
      label: c,
      data: aggregate(a),
      backgroundColor: COLORS[c] || "#C4B4CE",
      borderRadius: 1,
      stack: "dispatch",
      order: 2,
    }));
    if (demand) {
      const ds = values(sourceSeries("demand_total"));
      sets.push(line("Demanda COES", ds, "#51345E"));
      const peak = max(ds);
      if (peak != null)
        sets.push({
          ...line(
            "Máxima demanda",
            ds.map((x) => (x == null ? null : peak)),
            "#B69CC2",
            true,
          ),
          borderDash: [2, 4],
        });
    }
    if (comparison && previous)
      sets.push(
        line(
          title(previous.code),
          aggregate(viewAssets(previous)),
          "#AA97B6",
          true,
        ),
      );
    chart(
      id,
      "bar",
      idx().map((i) => D.times[i]),
      sets,
      "MW",
      {
        scales: {
          y: { ...opts().scales.y, stacked: true },
          x: { ...opts().scales.x, stacked: true },
        },
      },
    );
  }
  function dispatch(id, assets) {
    const sets = group(assets, "plant").map(([p, a], j) => ({
      type: "bar",
      label: p,
      data: aggregate(a),
      backgroundColor: PAL[j % PAL.length],
      borderRadius: 1,
      stack: "a",
    }));
    chart(
      id,
      "bar",
      idx().map((i) => D.times[i]),
      sets,
      "MW",
      {
        scales: {
          y: { ...opts().scales.y, stacked: true },
          x: { ...opts().scales.x, stacked: true },
        },
      },
    );
  }
  function ranking(id, assets, keyName = "company", limit = 15) {
    const groups = group(assets, keyName)
      .map(([label, a]) => ({ label, assets: a, value: total(a) }))
      .filter((a) => a.value != null)
      .sort((a, b) => b.value - a.value);
    const shown = groups.slice(0, limit);
    if (groups.length > limit) {
      shown.push({
        label: `Otras (${groups.length - limit})`,
        assets: groups.slice(limit).flatMap((a) => a.assets),
        value: groups.slice(limit).reduce((a, b) => a + b.value, 0),
      });
    }
    const cats = [...new Set(assets.map((a) => a.category))],
      sets = cats.map((c) => ({
        label: c,
        data: shown.map((g) => total(g.assets.filter((a) => a.category === c))),
        backgroundColor: COLORS[c] || "#b9a9c8",
        stack: "energy",
        borderRadius: 2,
      }));
    chart(
      id,
      "bar",
      shown.map((g) => g.label),
      sets,
      "GWh",
      {
        indexAxis: "y",
        scales: {
          x: {
            ...opts().scales.x,
            stacked: true,
            grid: { color: "#f3edf6" },
            title: { display: true, text: "GWh", font: { size: 9 } },
          },
          y: {
            ...opts().scales.y,
            stacked: true,
            title: { display: false },
            grid: { display: false },
            ticks: { font: { size: 9 } },
          },
        },
        plugins: {
          tooltip: {
            ...opts().plugins.tooltip,
            callbacks: {
              label: (c) => `${c.dataset.label}: ${fmt(c.parsed.x, 3)} GWh`,
            },
          },
        },
      },
    );
  }
  function factorChart(id, assets) {
    const g = group(assets, "technology");
    const averages = g.map(([, a]) => avg(aggregate(a))),
      caps = g.map(([, a]) => capacity(a));
    chart(
      id,
      "bar",
      g.map(([n]) => n || "Sin clasificación"),
      [
        {
          label: "Potencia media",
          data: averages,
          backgroundColor: "#A62E78",
          borderRadius: 2,
        },
        {
          label: "Potencia de referencia",
          data: caps,
          backgroundColor: "#E7D8EC",
          borderRadius: 2,
        },
        {
          ...line(
            "Factor de uso de potencia",
            averages.map((n, i) =>
              n != null && caps[i] > 0 ? (n / caps[i]) * 100 : null,
            ),
            "#E86820",
          ),
          yAxisID: "y1",
          pointRadius: 3,
          unit: "%",
        },
      ],
      "MW",
      {
        scales: {
          y1: {
            position: "right",
            min: 0,
            title: { display: true, text: "%", font: { size: 9 } },
            grid: { display: false },
            border: { display: false },
            ticks: { font: { size: 9 }, callback: (x) => fmt(x, 0) + "%" },
          },
        },
      },
    );
  }
  function dataCSV(rows, name) {
    const cell = (v) => {
      let s = String(v ?? "");
      if (typeof v !== "number" && /^[=+@\-]/.test(s)) s = "'" + s;
      return '"' + s.replaceAll('"', '""') + '"';
    };
    const blob = new Blob(
      ["\ufeff" + rows.map((r) => r.map(cell).join(";")).join("\r\n")],
      { type: "text/csv;charset=utf-8" },
    );
    downloadBlob(blob, name);
  }
  function downloadBlob(blob, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  function snapshotExport(assets) {
    exportRows = [
      [
        "Fecha",
        "Programa",
        "Anterior",
        "Nombre",
        "Empresa",
        "Tecnología",
        "Hora",
        "Actual MW",
        "Anterior MW",
        "Delta MW",
      ],
    ];
    const old = new Map((previous?.series || []).map((s) => [s.key, s]));
    for (const s of assets)
      for (const i of idx()) {
        const b = old.get(s.key)?.values[i];
        exportRows.push([
          S.day,
          S.code,
          previous?.code,
          s.plant,
          s.company,
          s.technology,
          D.times[i],
          s.values[i],
          b,
          subtract(s.values[i], b),
        ]);
      }
  }
  function executive() {
    const assets = gens(),
      oldAssets = gens(previous),
      gen = reportedGeneration(),
      oldGen = reportedGeneration(previous),
      inkia = assets.filter((a) => a.inkia),
      oldInkia = oldAssets.filter((a) => a.inkia),
      totalEnergy = energyValues(gen),
      oldEnergy = energyValues(oldGen),
      inkiaEnergy = total(inkia),
      oldInkiaEnergy = total(oldInkia),
      share =
        totalEnergy > 0 && inkiaEnergy != null
          ? (inkiaEnergy / totalEnergy) * 100
          : null,
      oldShare =
        oldEnergy > 0 && oldInkiaEnergy != null
          ? (oldInkiaEnergy / oldEnergy) * 100
          : null;
    const dem = values(sourceSeries("demand_total")),
      oldDem = values(sourceSeries("demand_total", previous)),
      costs = active?.series.filter((a) => a.role === "marginal_cost") || [],
      oldCosts =
        previous?.series.filter((a) => a.role === "marginal_cost") || [];
    const santa = (a) =>
      a.find((s) => norm(s.name).includes("SANTAROSA")) || a[0];
    const cmg = avg(values(santa(costs))),
      oldCmg = avg(values(santa(oldCosts)));
    const diff = gen.map((n, i) => subtract(n, oldGen[i])),
      peak = diff.some((n) => n != null)
        ? diff
            .filter((n) => n != null)
            .reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a), 0)
        : null;
    const periodText = `${D.times[idx()[0]] || "—"} – ${D.times[idx().at(-1)] || "—"} · ${idx().length} intervalos`;
    return {
      html: `<section class="stats-grid">${kpi("Máxima demanda", max(dem), "MW", previous ? max(oldDem) : null, "#A62E78", "Ventana publicada", "↗", 0)}${kpi("Energía programada", totalEnergy, "GWh", previous ? oldEnergy : null, "#682888", "Suma del período", "ϟ", 2)}${kpi("Generación INKIA", inkiaEnergy, "GWh", previous ? oldInkiaEnergy : null, "#E86820", "Kallpa · Orazul · Kondu · Joya Solar", "◈", 2)}${kpi("Participación INKIA", share, "%", previous ? oldShare : null, "#3599B8", "En el alcance seleccionado", "◔", 1)}${kpi("CMg Santa Rosa · promedio", cmg, "USD/MWh", previous ? oldCmg : null, "#A62E78", "Barra disponible en el anexo", "⌁", 2)}</section><div class="grid main-chart">${panel("summary-dispatch", "Despacho y demanda programada", "Generación por tecnología · " + periodText, "Los bloques se muestran desde la ventana seleccionada. La demanda utiliza el valor publicado por COES.", "tall")}<section class="panel"><div class="panel-head"><div><h2>Qué cambió en esta emisión</h2><p>Una lectura del impacto en el sistema</p></div><span class="head-icon">⇄</span></div><div class="insight-body"><span class="insight-eyebrow">MAYOR CAMBIO NETO DE POTENCIA</span><div class="insight-peak ${peak < 0 ? "negative" : ""}">${previous ? sign(peak) : "—"}<small>MW</small></div><div class="insight-sub">${previous ? h(title(S.code) + " frente a " + title(previous.code)) : "El PDO es el programa base del día."}</div><div class="insight-row"><span>Ventana publicada</span><b>${active?.published_intervals || 0} / 48</b></div><div class="insight-row"><span>Catálogo de tecnologías</span><b>${active?.catalog_coverage?.classified || 0} / ${active?.catalog_coverage?.total || 0}</b></div><div class="meter"><i style="width:${Math.min(100, ((active?.catalog_coverage?.classified || 0) / (active?.catalog_coverage?.total || 1)) * 100)}%"></i></div><button class="text-button" data-go="changes">Explorar variaciones por equipo ↗</button><div class="publication-text"><strong>MOTIVO SEGÚN COES</strong>${h(active?.publication?.cause || "Programa diario de operación. No corresponde una causa de reprogramación.")}</div></div></section></div><div class="grid two">${panel("company-energy", "Energía programada por empresa", "Distribución por tecnología · GWh", "Se deduplican los equipos que figuran en más de un bloque del anexo.", "tall")}${panel("marginal-costs", "Costos marginales previstos", "Barras publicadas en el anexo · USD/MWh", "El PBIX consulta ocho barras; el anexo de despacho actual publica las curvas disponibles aquí.", "tall")}</div>`,
      after() {
        stacked("summary-dispatch", assets, {
          demand: S.scope === "all" && !S.company && !S.plant && !S.technology,
        });
        ranking("company-energy", assets);
        const sets = costs.map((a, j) =>
          line(
            a.name.replace(" YUPANA(US$/MWh)", "").replace("Cmg ", ""),
            values(a),
            PAL[j],
          ),
        );
        if (previous) {
          const b = santa(oldCosts);
          if (b)
            sets.push(
              line(
                title(previous.code) + " · Santa Rosa",
                values(b),
                "#b8a7c4",
                true,
              ),
            );
        }
        chart(
          "marginal-costs",
          "line",
          idx().map((i) => D.times[i]),
          sets,
          "USD/MWh",
        );
        snapshotExport(assets);
      },
    };
  }
  function inkiaView() {
    const a = viewAssets(),
      b = viewAssets(previous),
      cap = capacity(a),
      mean = avg(aggregate(a)),
      oldMean = avg(aggregate(b)),
      e = total(a),
      oldE = total(b);
    return {
      html: `<section class="stats-grid four">${kpi("Energía INKIA", e, "GWh", previous ? oldE : null, "#A62E78", "Ventana seleccionada", "ϟ", 2)}${kpi("Potencia media", mean, "MW", previous ? oldMean : null, "#682888", "Promedio de los intervalos publicados", "⌁", 1)}${kpi("Potencia de referencia", cap, "MW", null, "#E86820", "Capacidad instalada según matrices", "▥", 1)}${kpi("Uso de potencia de referencia", cap > 0 && mean != null ? (mean / cap) * 100 : null, "%", null, "#3599B8", "Potencia media / potencia de referencia", "◔", 1)}</section><div class="grid two">${panel("inkia-thermal", "Despacho previsto térmico INKIA", "Unidades térmicas · MW", "Cada unidad conserva el nombre técnico del anexo.")}${panel("inkia-hydro", "Despacho previsto hidráulico INKIA", "Centrales hidráulicas · MW", "El comparador conserva las ventanas publicadas de cada emisión.")}${panel("inkia-rer", "Despacho previsto RER INKIA", "Generación solar y otras RER · MW", "Se utilizan los valores del COES; no se fuerzan ceros por horario.")}${panel("inkia-factor", "Potencia y factor por tecnología", "Potencia media, referencia del catálogo y factor de uso", "Matrices del usuario. Si falta potencia para alguna unidad del grupo, se advierte y no se calcula su factor.")}</div>`,
      after() {
        dispatch(
          "inkia-thermal",
          a.filter((s) => s.category === "Térmica"),
        );
        dispatch(
          "inkia-hydro",
          a.filter((s) => s.category === "Hidráulica"),
        );
        dispatch(
          "inkia-rer",
          a.filter((s) =>
            ["Solar", "Eólica", "Otras RER"].includes(s.category),
          ),
        );
        factorChart("inkia-factor", a);
        snapshotExport(a);
      },
    };
  }
  function othersView() {
    const a = viewAssets(),
      b = viewAssets(previous),
      renew = S.page === "renewable";
    return {
      html: `<section class="stats-grid four">${kpi("Energía de otras empresas", total(a), "GWh", previous ? total(b) : null, "#A62E78", "Alcance seleccionado", "ϟ", 2)}${kpi("Potencia media", avg(aggregate(a)), "MW", previous ? avg(aggregate(b)) : null, "#682888", "Media del período publicado", "⌁", 1)}${kpi("Centrales seleccionadas", new Set(a.map((s) => s.plant)).size, "", null, "#3599B8", "Catálogo de centrales", "▥", 0)}${kpi("Potencia de referencia", capacity(a), "MW", null, "#E86820", "Referencia técnica de las matrices", "◈", 1)}</section>${panel(renew ? "others-rer" : "others-conventional", renew ? "Despacho previsto eólico, solar y otras RER" : "Despacho previsto de otras empresas", "Generación por central · MW", "Los filtros de empresa, central y tecnología se aplican a esta vista.", "tall")}<div class="grid two">${panel(renew ? "others-rer-factor" : "others-factor", "Potencia y factor de uso por categoría", "Potencia media vs potencia de referencia", "El factor requiere potencia de referencia para todas las unidades del grupo. Un dato faltante se muestra sin factor.", "tall")}${panel(renew ? "others-rer-energy" : "others-energy", "Energía prevista por central", "Ordenada de mayor a menor · GWh", "Las centrales restantes se agrupan explícitamente cuando la selección supera quince.", "tall")}</div>`,
      after() {
        dispatch(renew ? "others-rer" : "others-conventional", a);
        factorChart(renew ? "others-rer-factor" : "others-factor", a);
        ranking(renew ? "others-rer-energy" : "others-energy", a, "plant");
        snapshotExport(a);
      },
    };
  }
  function hydroView() {
    const data = daily("hydrology")?.data,
      allRef = data?.reference_plants || data?.inkia_plants || [],
      rs = data?.reservoirs || [];
    const plants = allRef.filter(
      (p) =>
        S.hydroFlowScope === "all" ||
        (S.hydroFlowScope === "inkia" ? p.inkia : !p.inkia),
    );
    const scopedReservoirs = rs.filter(
      (r) =>
        S.reservoirScope === "all" ||
        (S.reservoirScope === "inkia" ? r.inkia : !r.inkia),
    );
    const owners = [...new Set(scopedReservoirs.map((r) => r.company))].sort();
    if (!owners.includes(S.reservoirCompany)) S.reservoirCompany = "";
    const available = scopedReservoirs
      .filter((r) => !S.reservoirCompany || r.company === S.reservoirCompany)
      .sort((a, b) => a.name.localeCompare(b.name));
    if (!available.some((r) => r.name === S.reservoir))
      S.reservoir =
        available.find((r) => norm(r.name).includes("CERRODELAGUILA"))?.name ||
        available[0]?.name ||
        "";
    const r = available.find((r) => r.name === S.reservoir),
      cqr = allRef.find((p) => norm(p.name) === "CARHUAQUERO"),
      cdp = allRef.find((p) => norm(p.name) === "CANONDELPATO"),
      cda = allRef.find((p) => norm(p.name) === "CERRODELAGUILA");
    const delta =
      r?.initial > 0 && r?.final != null
        ? ((r.final - r.initial) / r.initial) * 100
        : null;
    const scopeOptions = (value) =>
      [
        ["all", "Todas las empresas"],
        ["inkia", "INKIA"],
        ["others", "Otras empresas"],
      ]
        .map(
          ([v, t]) =>
            `<option value="${v}" ${value === v ? "selected" : ""}>${t}</option>`,
        )
        .join("");
    const rows = available.map((a) => [
      {
        html: `<button class="text-button" data-reservoir="${h(a.name)}">${h(a.name)}</button><small>${h(a.linked_plant || "Sin central vinculada en la matriz")}</small>`,
      },
      a.company,
      fmt(a.initial, 3),
      fmt(a.final, 3),
      {
        html: `<span class="${a.final - a.initial < 0 ? "negative" : "positive"}">${sign(subtract(a.final, a.initial), 3)}</span>`,
      },
      fmt(a.inflow, 2),
    ]);
    return {
      html: `${sourceBar(["hydrology"], "Hidrología diaria · todos los embalses publicados")}<section class="stats-grid three">${kpi("Volumen inicial", r?.initial, "Hm³", null, "#3599B8", r?.name || "Selecciona un embalse", "water", 3)}${kpi("Volumen final", r?.final, "Hm³", null, "#682888", "Extremo diario publicado", "water", 3)}${kpi("Variación de volumen", delta, "%", null, "#A62E78", "(Final − inicial) / inicial", "⇄", 2)}</section><section class="stats-grid three">${kpi("Factor hidráulico · CQR", cqr?.factor != null ? cqr.factor * 100 : null, "%", null, "#3599B8", "Referencia INKIA · Qturbinado / Qmáx.", "≈", 1)}${kpi("Factor hidráulico · CDP", cdp?.factor != null ? cdp.factor * 100 : null, "%", null, "#682888", "Referencia INKIA · Qturbinado / Qmáx.", "≈", 1)}${kpi("Factor hidráulico · CDA", cda?.factor != null ? cda.factor * 100 : null, "%", null, "#A62E78", "Referencia INKIA · Qturbinado / Qmáx.", "≈", 1)}</section><div class="grid two"><section class="panel"><div class="panel-head"><div><h2>Caudal y factor hidráulico por central</h2><p>La vista INKIA reproduce la selección del PBIX; puedes ampliar el alcance.</p></div></div><div class="panel-controls"><label>Centrales <select id="hydro-flow-scope">${scopeOptions(S.hydroFlowScope)}</select></label><span class="legend-note">${plants.length} centrales con referencia y valores del anexo.</span></div><div class="chart-box tall"><canvas id="hydro-flow" role="img" aria-label="Caudal y factor hidráulico por central"></canvas></div><div class="panel-note">El caudal de grupos G1/G2/G3 se suma una vez por central. Qmáx. procede de la matriz hidráulica.</div></section><section class="panel"><div class="panel-head"><div><h2>Volumen y caudal del embalse</h2><p>Extremos diarios · Hm³ y m³/s</p></div></div><div class="panel-controls"><label>Alcance de embalses <select id="reservoir-scope">${scopeOptions(S.reservoirScope)}</select></label><label>Empresa <select id="reservoir-company"><option value="">Todas las empresas</option>${owners.map((x) => `<option ${x === S.reservoirCompany ? "selected" : ""}>${h(x)}</option>`).join("")}</select></label><label>Embalse <select id="reservoir">${available.map((x) => `<option ${x.name === S.reservoir ? "selected" : ""}>${h(x.name)}</option>`).join("")}</select></label></div><div class="chart-box tall"><canvas id="hydro-volume" role="img" aria-label="Volúmenes inicial y final y caudal diario"></canvas></div><div class="panel-note">${available.length} embalses disponibles de ${rs.length} publicados. El anexo tiene extremos diarios, sin curva horaria; no se interpola.</div></section></div><section class="panel"><div class="panel-head"><div><h2>Balance de los embalses <span class="count-pill">${available.length}</span></h2><p>Selecciona un nombre para consultar su gráfica. Incluye las empresas fuera de INKIA.</p></div></div>${table(["EMBALSE / CENTRAL", "EMPRESA", "INICIAL Hm³", "FINAL Hm³", "Δ Hm³", "ENTRANTE m³/s"], rows, { id: "hydro-table", limit: 15 })}</section><section class="panel"><div class="panel-head"><div><h2>Caudales y parámetros de las centrales</h2><p>Valores observados, grupos incluidos y fila de la matriz utilizada.</p></div></div>${table(
        [
          "CENTRAL",
          "EMPRESA",
          "GRUPOS DEL ANEXO",
          "QTURB m³/s",
          "QMÁX m³/s",
          "FACTOR %",
          "MATRIZ / FILA",
        ],
        plants.map((p) => [
          p.display || p.name,
          p.company,
          p.source_units,
          fmt(p.turbined, 2),
          fmt(p.qmax, 2),
          fmt(p.factor != null ? p.factor * 100 : null, 1),
          `${p.matrix_file || "—"} · ${p.matrix_row || "—"}`,
        ]),
        { id: "hydro-parameters", limit: 15 },
      )}</section>`,
      after() {
        chart(
          "hydro-flow",
          "bar",
          plants.map((p) => p.display || p.name),
          [
            {
              label: "Caudal turbinado",
              data: plants.map((p) => p.turbined),
              backgroundColor: "#3599B8",
              borderRadius: 2,
            },
            {
              ...line(
                "Factor hidráulico",
                plants.map((p) => (p.factor != null ? p.factor * 100 : null)),
                "#A62E78",
              ),
              yAxisID: "y1",
              pointRadius: 3,
              unit: "%",
            },
          ],
          "m³/s",
          {
            scales: {
              y1: {
                position: "right",
                beginAtZero: true,
                grid: { display: false },
                border: { display: false },
                title: { display: true, text: "%", font: { size: 9 } },
                ticks: { font: { size: 9 }, callback: (v) => fmt(v, 0) + "%" },
              },
            },
          },
        );
        chart(
          "hydro-volume",
          "bar",
          ["Volumen inicial", "Caudal diario", "Volumen final"],
          [
            {
              label: "Volumen · Hm³",
              data: [r?.initial ?? null, null, r?.final ?? null],
              backgroundColor: ["#CDB7DC", "#EDE3F3", "#A62E78"],
              unit: "Hm³",
              borderRadius: 3,
            },
            {
              label: "Caudal entrante · m³/s",
              type: "line",
              data: [null, r?.inflow ?? null, null],
              yAxisID: "y1",
              pointRadius: 6,
              backgroundColor: "#3599B8",
              borderColor: "#3599B8",
              unit: "m³/s",
            },
          ],
          "Hm³",
          {
            scales: {
              y1: {
                position: "right",
                beginAtZero: true,
                grid: { display: false },
                border: { display: false },
                title: { display: true, text: "m³/s", font: { size: 9 } },
                ticks: { font: { size: 9 } },
              },
            },
          },
        );
        exportRows = [
          [
            "Fecha",
            "Embalse",
            "Empresa",
            "Volumen inicial Hm3",
            "Volumen final Hm3",
            "Delta Hm3",
            "Caudal entrante m3/s",
          ],
          ...available.map((a) => [
            S.day,
            a.name,
            a.company,
            a.initial,
            a.final,
            subtract(a.final, a.initial),
            a.inflow,
          ]),
        ];
      },
    };
  }
  function reserveView() {
    const data = rsf(),
      units = (data?.units || []).filter(
        (a) =>
          (S.scope === "all" || (S.scope === "inkia" ? a.inkia : !a.inkia)) &&
          (!S.company || a.company === S.company),
      );
    if (!units.some((a) => a.urs === S.urs)) S.urs = "";
    const chosen = units.filter((a) => !S.urs || a.urs === S.urs),
      byDirection = (dir) =>
        idx().map((i) => {
          const vals = chosen.map((a) => a[dir][i]).filter((x) => x != null);
          return vals.length ? vals.reduce((a, b) => a + b, 0) : null;
        });
    let up = byDirection("up"),
      down = byDirection("down");
    if (data && S.scope === "all" && !S.company && !S.urs) {
      up = idx().map((i) => data.totals.up[i]);
      down = idx().map((i) => data.totals.down[i]);
    }
    const systemUp = data
        ? energyValues(idx().map((i) => data.totals.up[i]))
        : null,
      systemDown = data
        ? energyValues(idx().map((i) => data.totals.down[i]))
        : null;
    const delegations = daily("delegations")?.data || [],
      links = daily("links")?.data || [];
    const dels = delegations,
      lnks = links;
    const rpfRows = (rows) =>
      rows.map((r) => [
        r.code,
        r.from,
        r.to,
        `${r.start_date} ${r.start}`,
        `${r.end_date} ${r.end}`,
        fmt(r.percent, 0),
        r.backup || "—",
      ]);
    return {
      html: `<div class="source-bar"><span><strong>Reserva secundaria ${h(data?.source?.code ? title(data.source.code) : "no disponible")}</strong> · ${h(S.day)}${data?.source?.code && data.source.code !== S.code ? ` · no se ha publicado una reserva específica para ${h(title(S.code))}; se identifica el PDO como fuente.` : "."} RPF: anexos diarios de vinculaciones y delegaciones.</span>${data?.source ? `<a href="${h(encodeURI(data.source.file))}" download>Ver reserva original ↗</a>` : ""}</div><section class="stats-grid">${kpi("URS programadas", data && idx().some((i) => data.totals.up[i] != null || data.totals.down[i] != null) ? new Set(chosen.filter((u) => idx().some((i) => [u.up[i], u.down[i]].some((x) => x != null && Math.abs(x) > 0.0001))).map((u) => u.urs)).size : null, "", null, "#682888", "URS con reserva publicada en la selección", "▥", 0)}${kpi("Reserva hacia arriba · media", avg(up), "MW", null, "#A62E78", "Media de los valores numéricos publicados", "↑", 1)}${kpi("Reserva hacia abajo · media", avg(down), "MW", null, "#3599B8", "Media publicada · magnitud positiva DOWN", "↓", 1)}${kpi("Participación central · UP", S.urs && systemUp > 0 && avg(up) != null ? (energyValues(up) / systemUp) * 100 : null, "%", null, "#E86820", "Selecciona una URS para calcular su participación", "◔", 1)}${kpi("Participación central · DOWN", S.urs && systemDown > 0 && avg(down) != null ? (energyValues(down) / systemDown) * 100 : null, "%", null, "#A62E78", "Asignación acumulada / reserva del sistema", "◔", 1)}</section><section class="panel" data-chart="reserve-dispatch"><div class="panel-head"><div><h2>Reserva por unidad / central</h2><p>Hacia arriba (+) y hacia abajo (−) · MW</p></div></div><div class="panel-controls"><label>Unidad de regulación <select id="urs"><option value="">Todas las URS del alcance</option>${units.map((u) => `<option value="${h(u.urs)}" ${S.urs === u.urs ? "selected" : ""}>${h(u.name + " · " + u.urs)}</option>`).join("")}</select></label><span class="legend-note">Medias de valores publicados; vacíos excluidos. Participación: asignación acumulada frente al total del sistema.</span></div><div class="chart-box tall"><canvas id="reserve-dispatch" role="img" aria-label="Reserva secundaria por unidad y hora"></canvas></div><div class="panel-note"><span>UP se grafica en positivo y DOWN en negativo. Los vacíos de cada unidad permanecen sin valor.</span><span>Pico UP ${fmt(max(up))} MW · Pico DOWN ${fmt(max(down))} MW</span></div></section><section class="panel"><div class="panel-head"><div><h2>Delegaciones RPF <span class="count-pill">${dels.length}</span></h2><p>Anexo diario completo · los filtros superiores se aplican a RSF, no a esta tabla.</p></div></div><div style="height:16px"></div>${table(["CÓDIGO", "DELEGANTE", "ENCARGADA", "INICIO", "FINAL", "CD %", "RESPALDO"], rpfRows(dels), { id: "delegations", limit: 12 })}</section><section class="panel"><div class="panel-head"><div><h2>Vinculaciones RPF <span class="count-pill">${lnks.length}</span></h2><p>Anexo diario completo · central/grupo vinculante y equipo RPF encargado.</p></div></div><div style="height:16px"></div>${table(["CÓDIGO", "VINCULANTE", "EQUIPO RPF", "INICIO", "FINAL", "REQUIPO %", "RESPALDO"], rpfRows(lnks), { id: "links", limit: 12 })}</section>`,
      after() {
        const sets = [];
        chosen.forEach((u, j) => {
          sets.push({
            label: u.name + " ↑",
            data: idx().map((i) => u.up[i]),
            backgroundColor: PAL[j % PAL.length],
            stack: "reserve",
          });
          sets.push({
            label: u.name + " ↓",
            data: idx().map((i) => (u.down[i] == null ? null : -u.down[i])),
            backgroundColor: PAL[j % PAL.length] + "88",
            stack: "reserve",
          });
        });
        chart(
          "reserve-dispatch",
          "bar",
          idx().map((i) => D.times[i]),
          sets,
          "MW",
          {
            scales: {
              y: { ...opts().scales.y, stacked: true },
              x: { ...opts().scales.x, stacked: true },
            },
          },
        );
        exportRows = [
          ["Fecha", "Fuente", "URS", "Central", "Hora", "UP MW", "DOWN MW"],
          ...chosen.flatMap((u) =>
            idx().map((i) => [
              S.day,
              data?.source?.code,
              u.urs,
              u.name,
              D.times[i],
              u.up[i],
              u.down[i],
            ]),
          ),
        ];
      },
    };
  }
  function eventMatches(r) {
    return (
      (S.scope === "all" || (S.scope === "inkia" ? r.inkia : !r.inkia)) &&
      (!S.company || (r.company_canonical || r.company) === S.company) &&
      (!S.plant ||
        norm(r.location).includes(
          norm(S.plant.replace(/^(CH|CT|CS|CE) /, "")),
        )) &&
      (!S.search || norm(Object.values(r).join(" ")).includes(norm(S.search)))
    );
  }
  function maintenanceView() {
    const allMaint = (daily("maintenance")?.data || []).filter(eventMatches),
      allRestrictions = (daily("restrictions")?.data || []).filter(
        eventMatches,
      ),
      isMaint = S.eventView === "maintenance",
      base = isMaint ? allMaint : allRestrictions,
      categories = [
        ...new Set(base.map((r) => r.category || "Restricción operativa")),
      ].sort();
    if (!categories.includes(S.eventCategory)) S.eventCategory = "";
    const rows = base.filter(
        (r) =>
          !S.eventCategory ||
          (r.category || "Restricción operativa") === S.eventCategory,
      ),
      inkiaCount = allMaint.filter((r) => r.inkia).length;
    const sumMW = allMaint
      .filter((r) => r.mw != null)
      .reduce((n, r) => n + r.mw, 0);
    const tableRows = rows.map((r) => [
      r.company,
      r.location,
      r.equipment,
      r.start,
      r.end,
      { html: `<div class="text-wrap description">${h(r.description)}</div>` },
      { html: badge(r.category || "Restricción", "neutral") },
    ]);
    return {
      html: `${sourceBar(["maintenance", "restrictions"], "Intervenciones y restricciones del programa diario")}<section class="stats-grid four">${kpi("Mantenimientos programados", daily("maintenance") ? allMaint.length : null, "eventos", null, "#A62E78", "Registros publicados por COES", "▥", 0)}${kpi("MW reportados en eventos", daily("maintenance") ? sumMW : null, "MW", null, "#E86820", "Suma de MW de eventos; no es indisponibilidad simultánea", "ϟ", 1)}${kpi("Mantenimientos INKIA", daily("maintenance") ? inkiaCount : null, "eventos", null, "#682888", "Empresas del grupo INKIA", "◈", 0)}${kpi("Restricciones INKIA", daily("restrictions") ? allRestrictions.filter((r) => r.inkia).length : null, "eventos", null, "#3599B8", "Restricciones operativas publicadas", "⌁", 0)}</section><div class="grid two">${panel("maintenance-categories", "Distribución de mantenimientos por categoría", "Cantidad de eventos por estado y tipo de equipo", "Clasificación basada en el área del equipo COES y su disponibilidad; desconocidos quedan en Otros.", "tall")}${panel("maintenance-ranking", "Ranking de mayor indisponibilidad reportada", "MW consignados en los eventos · no necesariamente simultáneos", "No se calcula una indisponibilidad instantánea sumando eventos superpuestos.", "tall")}</div><section class="panel"><div class="panel-head"><div><h2>Mantenimientos y restricciones operativas</h2><p>Detalle de empresa, ubicación, equipo y descripción.</p></div></div><div class="panel-controls"><label>Vista <select id="event-view"><option value="maintenance" ${isMaint ? "selected" : ""}>Mantenimientos</option><option value="restrictions" ${!isMaint ? "selected" : ""}>Restricciones operativas</option></select></label><label>Categoría <select id="event-category"><option value="">Todas las categorías</option>${categories.map((c) => `<option ${S.eventCategory === c ? "selected" : ""}>${h(c)}</option>`).join("")}</select></label><input type="search" class="search" id="event-search" value="${h(S.search)}" placeholder="Buscar empresa, equipo o descripción…" aria-label="Buscar eventos"></div>${table(["EMPRESA", "UBICACIÓN", "EQUIPO", "INICIO", "FINAL", "DESCRIPCIÓN", "CATEGORÍA"], tableRows, { id: "events-table", limit: 15 })}</section>`,
      after() {
        const counts = new Map();
        for (const r of allMaint)
          counts.set(r.category, (counts.get(r.category) || 0) + 1);
        chart(
          "maintenance-categories",
          "bar",
          [...counts.keys()],
          [
            {
              label: "Eventos",
              data: [...counts.values()],
              backgroundColor: [...counts.keys()].map((_, i) => PAL[i]),
              borderRadius: 3,
            },
          ],
          "eventos",
          {
            indexAxis: "y",
            scales: {
              x: {
                ...opts().scales.x,
                beginAtZero: true,
                grid: { color: "#f3edf6" },
              },
              y: {
                ...opts().scales.y,
                title: { display: false },
                grid: { display: false },
                ticks: { font: { size: 10 } },
              },
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                ...opts().plugins.tooltip,
                callbacks: { label: (c) => fmt(c.parsed.x, 0) + " eventos" },
              },
            },
          },
        );
        const ranks = [...allMaint]
          .filter((r) => r.mw > 0)
          .sort((a, b) => b.mw - a.mw)
          .slice(0, 12);
        chart(
          "maintenance-ranking",
          "bar",
          ranks.map((r) => r.location + " · " + r.equipment),
          [
            {
              label: "MW del evento",
              data: ranks.map((r) => r.mw),
              backgroundColor: "#A62E78",
              borderRadius: 2,
            },
          ],
          "MW",
          {
            indexAxis: "y",
            scales: {
              x: {
                ...opts().scales.x,
                beginAtZero: true,
                grid: { color: "#f3edf6" },
              },
              y: {
                ...opts().scales.y,
                title: { display: false },
                grid: { display: false },
                ticks: { font: { size: 9 } },
              },
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                ...opts().plugins.tooltip,
                callbacks: { label: (c) => fmt(c.parsed.x, 1) + " MW" },
              },
            },
          },
        );
        exportRows = [
          [
            "Fecha",
            "Vista",
            "Empresa",
            "Ubicación",
            "Equipo",
            "Inicio",
            "Final",
            "Descripción",
            "MW de evento",
            "Categoría",
          ],
          ...rows.map((r) => [
            S.day,
            S.eventView,
            r.company,
            r.location,
            r.equipment,
            r.start,
            r.end,
            r.description,
            r.mw,
            r.category || "Restricción",
          ]),
        ];
      },
    };
  }
  function electricalView() {
    const d = daily("electrical"),
      data = d?.data,
      records = data?.loadings || [],
      pages = [...new Set(records.map((r) => String(r.page)))];
    if (!pages.includes(S.electricalPage)) S.electricalPage = "";
    const selected = records
      .filter((r) => !S.electricalPage || String(r.page) === S.electricalPage)
      .filter((r) => !S.search || norm(r.equipment).includes(norm(S.search)));
    const sorted = [...selected].sort((a, b) => b.loading - a.loading),
      flows = (active?.series || []).filter((a) => a.role === "flow");
    return {
      html: `${sourceBar(["electrical"], "Análisis eléctrico oficial del PDI")}<div class="flow-banner"><span><b>Resultados publicados, con trazabilidad al PDF.</b> La imagen de contingencias del PBIX se sustituye por las filas de cargabilidad que pueden extraerse del anexo COES.</span>${data?.pdf_file ? `<a class="button secondary small" href="${h(encodeURI(data.pdf_file))}" target="_blank" rel="noopener">Abrir informe eléctrico ↗</a>` : ""}</div><section class="stats-grid three">${kpi("Filas de cargabilidad extraídas", data ? records.length : null, "", null, "#682888", "Solo filas tabulares explícitas del PDF", "▥", 0)}${kpi("Filas superiores al 100%", data ? records.filter((r) => r.loading > 100).length : null, "", null, "#A62E78", "Son resultados del anexo, no simulaciones nuevas", "↗", 0)}${kpi("Mayor cargabilidad reportada", max(records.map((r) => r.loading)), "%", null, "#E86820", "Máximo de la fila agrupada publicada", "⌁", 1)}</section><div class="grid two">${panel("electrical-loading", "Cargabilidad reportada por equipo", "Porcentajes explícitos del informe PDI", "El PDF no publica la misma tabla Base/N−1 del ejemplo del PBIX. No se inventan columnas ni casos de simulación.", "tall")}${panel("electrical-flows", "Flujos previstos en los enlaces", "Curvas del anexo de despacho seleccionado · MW", "Los flujos de potencia no se convierten en porcentajes de carga sin una capacidad nominal publicada.", "tall")}</div><section class="panel"><div class="panel-head"><div><h2>Filas del informe eléctrico</h2><p>El equipo y la página permiten revisar cada porcentaje en su documento original.</p></div></div><div class="panel-controls"><label>Página del informe <select id="electrical-page"><option value="">Todas las páginas extraídas</option>${pages.map((p) => `<option value="${p}" ${S.electricalPage === p ? "selected" : ""}>Página ${p}</option>`).join("")}</select></label><input type="search" id="electrical-search" class="search" placeholder="Buscar equipo…" value="${h(S.search)}" aria-label="Buscar equipo eléctrico"></div>${table(
        [
          "EQUIPO / GRUPO",
          "VALOR REPORTADO",
          "MÁXIMO DE LA FILA",
          "PÁGINA",
          "CONTEXTO",
        ],
        sorted.map((r) => [
          r.equipment,
          r.reported,
          {
            html: badge(
              fmt(r.loading, 1) + "%",
              r.loading > 100 ? "danger" : "info",
            ),
          },
          r.page,
          { html: `<div class="text-wrap">${h(r.context)}</div>` },
        ]),
        { id: "electrical-table", limit: 15 },
      )}</section>${data?.pdf_file ? `<section class="panel"><div class="panel-head"><div><h2>Documento de análisis eléctrico</h2><p>Informe original del COES para la fecha seleccionada.</p></div><a class="button secondary small" href="${h(encodeURI(data.pdf_file))}" download>↓ Descargar PDF</a></div><div class="pdf-frame-wrapper"><iframe class="pdf-frame" title="Informe eléctrico del COES" loading="lazy" src="${h(encodeURI(data.pdf_file))}#toolbar=1"></iframe></div></section>` : ""}`,
      after() {
        const ranks = sorted.slice(0, 15);
        chart(
          "electrical-loading",
          "bar",
          ranks.map((r) => r.equipment),
          [
            {
              label: "Máximo reportado por fila",
              data: ranks.map((r) => r.loading),
              backgroundColor: ranks.map((r) =>
                r.loading > 100 ? "#A62E78" : "#C2A1D2",
              ),
              borderRadius: 2,
            },
          ],
          "%",
          {
            indexAxis: "y",
            scales: {
              x: {
                ...opts().scales.x,
                beginAtZero: true,
                grid: { color: "#f3edf6" },
              },
              y: {
                ...opts().scales.y,
                title: { display: false },
                grid: { display: false },
                ticks: { font: { size: 9 } },
              },
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                ...opts().plugins.tooltip,
                callbacks: {
                  label: (c) =>
                    fmt(c.parsed.x, 1) +
                    "% · página " +
                    ranks[c.dataIndex].page,
                },
              },
            },
          },
        );
        chart(
          "electrical-flows",
          "line",
          idx().map((i) => D.times[i]),
          flows.map((a, j) =>
            line(a.name.replace("FLUJO ", ""), values(a), PAL[j % PAL.length]),
          ),
          "MW",
        );
        exportRows = [
          [
            "Fecha",
            "Equipo",
            "Valor reportado",
            "Máximo de fila %",
            "Página",
            "Contexto",
          ],
          ...selected.map((r) => [
            S.day,
            r.equipment,
            r.reported,
            r.loading,
            r.page,
            r.context,
          ]),
        ];
      },
    };
  }
  function changeAssets() {
    return (active?.series || []).filter((a) =>
      S.changeKind === "generation"
        ? a.generation && scoped(a)
        : S.changeKind === "demand"
          ? ["demand_total", "model_demand", "demand_area"].includes(a.role)
          : S.changeKind === "cost"
            ? a.role === "marginal_cost"
            : a.role === "flow",
    );
  }
  function changeRows() {
    const old = new Map((previous?.series || []).map((a) => [a.key, a]));
    return changeAssets()
      .map((a) => {
        const b = old.get(a.key),
          d = idx().map((i) => subtract(a.values[i], b?.values[i]));
        const valid = d.filter((v) => v != null),
          peak = valid.length
            ? valid.reduce((x, y) => (Math.abs(y) > Math.abs(x) ? y : x))
            : null,
          pi = d.indexOf(peak),
          energy = valid.length ? valid.reduce((x, y) => x + y, 0) * 0.5 : null;
        return {
          a,
          b,
          d,
          peak,
          time: peak == null ? null : D.times[idx()[pi]],
          alerts: valid.filter((x) => Math.abs(x) >= S.threshold).length,
          energy,
        };
      })
      .sort((a, b) => Math.abs(b.peak || 0) - Math.abs(a.peak || 0));
  }
  function changesView() {
    const rows = changeRows(),
      unit = S.changeKind === "cost" ? "USD/MWh" : "MW",
      r = rows.find((r) => r.a.key === S.series) || rows[0];
    S.series = r?.a.key || "";
    const changed = rows.filter(
        (r) => r.peak != null && Math.abs(r.peak) > 0.000001,
      ),
      alert = rows.filter((r) => r.alerts > 0),
      display = rows.filter(
        (r) =>
          !S.search || norm(r.a.plant || r.a.name).includes(norm(S.search)),
      );
    const heat = changed.slice(0, 12),
      int = idx(),
      largest = Math.max(
        ...heat.flatMap((r) => r.d.map((n) => Math.abs(n || 0))),
        1,
      );
    const heatHTML = heat
      .map(
        (r) =>
          `<div class="heat-row"><button data-series="${h(r.a.key)}" title="${h(r.a.plant || r.a.name)}">${h(r.a.plant || r.a.name)}</button>${r.d.map((d, i) => `<button class="heat-cell" data-series="${h(r.a.key)}" aria-label="${h(r.a.name)}, ${h(D.times[int[i]])}: ${h(sign(d))} ${h(unit)}" title="${h(r.a.name)} · ${D.times[int[i]]}\nActual ${fmt(r.a.values[int[i]], 2)} · Anterior ${fmt(r.b?.values[int[i]], 2)}\nΔ ${sign(d, 2)} ${unit}" style="background:${d == null ? "repeating-linear-gradient(45deg,#eee6f2,#eee6f2 2px,#fff 2px,#fff 4px)" : Math.abs(d) < 0.000001 ? "#F3EEF7" : d > 0 ? `rgba(166,46,120,${0.12 + 0.88 * Math.min(Math.abs(d) / largest, 1)})` : `rgba(53,153,184,${0.12 + 0.88 * Math.min(Math.abs(d) / largest, 1)})`}"></button>`).join("")}</div>`,
      )
      .join("");
    const tableData = display.map((r) => [
      {
        html: `<strong>${h(r.a.plant || r.a.name)}</strong><small>${h(r.a.company || r.a.role)}</small>`,
      },
      r.a.category || r.a.role,
      {
        html: `<span class="${r.peak > 0 ? "positive" : "negative"}">${sign(r.peak)} ${h(unit)}</span>`,
      },
      r.time || "—",
      r.a.unit === "MW" ? sign(r.energy, 1) + " MWh" : "—",
      r.alerts
        ? { html: badge("Alto · " + r.alerts + " int.", "danger") }
        : {
            html: badge(
              r.peak == null
                ? "Sin pares"
                : Math.abs(r.peak) < 0.000001
                  ? "Sin cambio"
                  : "Moderado",
              "neutral",
            ),
          },
    ]);
    return {
      html: `<section class="stats-grid four">${kpi("Mayor variación por serie", previous ? rows[0]?.peak : null, unit, null, "#A62E78", rows[0]?.a.plant || "Selecciona dos emisiones consecutivas", "⇄", 1)}${kpi("Series con variaciones", previous ? changed.length : null, "", null, "#682888", "Datos publicados en ambos programas", "▥", 0)}${kpi("Series de alto impacto", previous ? alert.length : null, "", null, "#E86820", "Al menos un intervalo supera el umbral", "↗", 0)}${kpi("Intervalos comparables", previous ? idx().filter((_, j) => rows.some((r) => r.d[j] != null)).length : null, "", null, "#3599B8", "Intervalos con al menos un par numérico", "⌁", 0)}</section><section class="panel"><div class="panel-head"><div><h2>Actual frente al programa anterior</h2><p>Explora una unidad o variable, conservando sus valores y sus vacíos.</p></div></div><div class="panel-controls"><label>Conjunto <select id="change-kind"><option value="generation" ${S.changeKind === "generation" ? "selected" : ""}>Generación</option><option value="demand" ${S.changeKind === "demand" ? "selected" : ""}>Demanda</option><option value="cost" ${S.changeKind === "cost" ? "selected" : ""}>Costos marginales</option><option value="flow" ${S.changeKind === "flow" ? "selected" : ""}>Flujos de potencia</option></select></label><label>Serie <select id="change-series">${rows.map((x) => `<option value="${h(x.a.key)}" ${S.series === x.a.key ? "selected" : ""}>${h(x.a.plant || x.a.name)}</option>`).join("")}</select></label><label class="right">Umbral <input class="number" id="threshold" type="number" min="0.01" max="100000" step="1" value="${S.threshold}">${h(unit)}</label></div><div class="chart-box tall"><canvas id="change-trend" role="img" aria-label="Comparación de programas de la serie seleccionada"></canvas></div><div class="panel-note"><span>${r ? h(r.a.name) + " · " + h(r.a.unit || "") : ""} · Las horas no publicadas y las celdas vacías no se convierten en cero.</span></div></section><section class="panel"><div class="panel-head"><div><h2>Mapa de variaciones <span class="count-pill">Top 12</span></h2><p>Magenta: aumento · Azul: reducción · Rayado: sin par comparable</p></div></div><div class="heatmap-scroll"><div class="heatmap-grid" style="--n:${int.length}"><div class="heat-row head"><span>EQUIPO / INTERVALO</span>${int.map((i, j) => `<span>${j % 4 === 3 || j === int.length - 1 ? D.times[i] : ""}</span>`).join("")}</div>${heatHTML || '<div class="missing">Sin variaciones numéricas comparables en esta selección.</div>'}</div></div><div class="panel-note"><span>Selecciona un equipo para cambiar su curva. Los máximos usan el valor absoluto del cambio.</span></div></section><section class="panel"><div class="panel-head"><div><h2>Detalle de variaciones por equipo</h2><p>Ordenado por el mayor impacto absoluto.</p></div><button data-action="export" class="button secondary small">↓ Exportar CSV</button></div><div class="panel-controls"><input id="change-search" class="search" type="search" value="${h(S.search)}" placeholder="Buscar equipo…" aria-label="Buscar variaciones"></div>${table(["EQUIPO / VARIABLE", "TIPO", "Δ MÁXIMO", "HORA", "Δ ENERGÍA", "IMPACTO"], tableData, { id: "changes-table", limit: 15 })}</section>${
        r
          ? `<section class="panel"><div class="panel-head"><div><h2>Valores de ${h(r.a.plant || r.a.name)}</h2><p>Consulta del intervalo hasta la celda de origen del programa nuevo.</p></div></div><div style="height:15px"></div>${table(
              ["HORA", "ANTERIOR", "ACTUAL", "Δ", "CELDA ACTUAL"],
              int.map((i, j) => [
                D.times[i],
                fmt(r.b?.values[i], 2),
                fmt(r.a.values[i], 2),
                sign(r.d[j], 2),
                i < r.a.first_interval_index
                  ? "—"
                  : r.a.column +
                    (r.a.first_data_row + i - r.a.first_interval_index),
              ]),
              { id: "interval-table", limit: 48 },
            )}</section>`
          : ""
      }`,
      after() {
        chart(
          "change-trend",
          "line",
          int.map((i) => D.times[i]),
          [
            line(
              previous ? title(previous.code) : "Sin anterior",
              r ? values(r.b) : [],
              "#B39BC2",
              true,
            ),
            line(title(S.code), r ? values(r.a) : [], "#A62E78"),
          ],
          unit,
        );
        exportRows = [
          [
            "Fecha",
            "Actual",
            "Anterior",
            "Serie",
            "Unidad",
            "Hora",
            "Anterior",
            "Actual",
            "Delta",
          ],
          ...rows.flatMap((r) =>
            int.map((i, j) => [
              S.day,
              S.code,
              previous?.code,
              r.a.name,
              r.a.unit,
              D.times[i],
              r.b?.values[i],
              r.a.values[i],
              r.d[j],
            ]),
          ),
        ];
      },
    };
  }
  function archiveView() {
    const all = D.versions.filter(
      (v) =>
        v.day === S.day &&
        (S.revisions || v.current) &&
        (!S.search ||
          norm(v.code + " " + v.filename + " " + v.publication?.cause).includes(
            norm(S.search),
          )),
    );
    const rows = all.map((v) => [
      {
        html: `<strong>${h(title(v.code))}${v.current ? "" : " · revisión anterior"}</strong><small class="file-name">${h(v.filename)}</small>`,
      },
      v.publication?.effective_from || "Programa base",
      {
        html: `<div class="text-wrap">${h(v.publication?.cause || "Programa diario de operación")}</div>`,
      },
      {
        html:
          badge(
            v.structured ? "Estructurado" : "Original conservado",
            v.structured ? "success" : "warn",
          ) +
          `<small>${v.series.length} columnas · ${v.published_intervals} horas publicadas</small>`,
      },
      {
        html: `<a href="${h(v.file)}" download>↓ Excel original</a><small title="${h(v.digest)}">SHA-256 ${h(v.digest.slice(0, 12))}…</small>`,
      },
    ]);
    const files = extra().files || [];
    return {
      html: `<section class="stats-grid three">${kpi("Originales / revisiones", all.length, "", null, "#A62E78", "Fecha seleccionada", "▥", 0)}${kpi("Anexos complementarios", files.length, "", null, "#682888", "Hidrología, reservas, RPF, PDI y restricciones", "▤", 0)}${kpi("Fechas archivadas", days.length, "", null, "#3599B8", "Historial local conservado", "⌁", 0)}</section><section class="panel"><div class="panel-head"><div><h2>Repositorio de originales</h2><p>Programas de operación con su huella y fecha de emisión.</p></div><a class="button secondary small" href="manifest.json" download>↓ Catálogo JSON</a></div><div class="panel-controls"><input type="search" id="archive-search" class="search" placeholder="Buscar archivo, emisión o motivo…" value="${h(S.search)}" aria-label="Buscar archivo"><label><input type="checkbox" id="revisions" ${S.revisions ? "checked" : ""}>Incluir revisiones anteriores</label></div>${table(["PROGRAMA / ARCHIVO", "VIGENCIA", "MOTIVO COES", "LECTURA", "DESCARGA"], rows, { id: "archive-table", limit: 15 })}</section><section class="panel"><div class="panel-head"><div><h2>Anexos complementarios de la jornada</h2><p>Las fuentes conservan su versión PDO, PDI o reprograma.</p></div></div><div style="height:15px"></div>${table(
        ["FUENTE", "VERSIÓN", "ARCHIVO", "DESCARGA"],
        files.map((f) => [
          f.kind,
          f.code,
          { html: `<span class="file-name">${h(f.filename)}</span>` },
          { html: `<a href="${h(encodeURI(f.file))}" download>↓ Original</a>` },
        ]),
        { id: "annex-table", limit: 30 },
      )}</section>`,
      after() {
        exportRows = [
          ["Fecha", "Version", "Archivo", "SHA256", "Fuente", "Ruta"],
          ...all.map((v) => [
            v.day,
            v.code,
            v.filename,
            v.digest,
            v.source,
            v.file,
          ]),
        ];
      },
    };
  }
  function noteKey() {
    return (
      "kallpa-rdo-note:" +
      S.day +
      ":" +
      S.code +
      ":" +
      (active?.digest?.slice(0, 10) || "none")
    );
  }
  function storedNote() {
    try {
      return localStorage.getItem(noteKey()) || "";
    } catch (_) {
      return "";
    }
  }
  function notesView() {
    return {
      html: `<div class="notes-layout"><section class="panel"><div class="panel-head"><div><h2>Bitácora de ${h(title(S.code))}</h2><p>${h(S.day)} · notas asociadas a esta emisión y a su revisión.</p></div></div><div class="notes-editor"><textarea id="notes-text" aria-label="Apuntes de la operación" placeholder="Registra aquí observaciones, decisiones, pendientes y responsables…"></textarea><div class="spark-caption" id="notes-status">Guardado local en este navegador. Exporta para conservar una copia.</div><div class="panel-controls" style="padding:15px 0 0"><button class="button primary" data-action="export-notes">↓ Exportar apuntes</button><label class="button secondary">↑ Importar apuntes<input type="file" id="import-notes" accept="application/json,.json" class="hidden"></label></div></div></section><section class="panel"><div class="panel-head"><div><h2>Contexto de la emisión</h2><p>Una referencia para documentar el cambio.</p></div></div><div class="notes-info"><span class="field-label">PROGRAMA SELECCIONADO</span>${h(title(S.code))}${previous ? " vs " + h(title(previous.code)) : ""}<br><br><span class="field-label">MOTIVO COES</span>${h(active?.publication?.cause || "Programa diario de operación")}<br><br><span class="field-label">VIGENCIA</span>${h(active?.publication?.effective_from || "Programa base")}<br><br><span class="field-label">HUELLA DEL ORIGINAL</span><code style="word-break:break-all;font-size:9px">${h(active?.digest || "—")}</code><br><br>Los apuntes no modifican los datos del COES. Se almacenan localmente y no se envían a servicios externos.</div></section></div>`,
      after() {
        $("notes-text").value = storedNote();
        exportRows = [
          ["Fecha", "Programa", "SHA256", "Apuntes"],
          [S.day, S.code, active?.digest, storedNote()],
        ];
      },
    };
  }
  function catalogView() {
    const c = D.catalog || {
        alerts: [],
        inventory: [],
        events: [],
        sources: [],
        references: { plants: [], hydrology: [], units: [] },
      },
      query = norm(S.search),
      match = (r) => !query || norm(JSON.stringify(r)).includes(query);
    const tabs = [
      ["alerts", "Avisos y parámetros pendientes"],
      ["inventory", "Inventario observado"],
      ["parameters", "Parámetros de las matrices"],
      ["history", "Historial de cambios"],
    ];
    const value = (x) =>
      x == null ? "—" : typeof x === "object" ? JSON.stringify(x) : String(x);
    let headers, rows, exportData;
    if (S.catalogTab === "inventory") {
      headers = [
        "TIPO / CÓDIGO",
        "NOMBRE",
        "EMPRESA",
        "TECNOLOGÍA",
        "POTENCIA REF. MW",
        "ESTADO",
        "PRIMERA / ÚLTIMA APARICIÓN",
      ];
      const records = c.inventory.filter(match);
      rows = records.map((r) => [
        r.kind + " · " + (r.code || "—"),
        r.display || r.name,
        r.company || "—",
        r.technology || "—",
        fmt(r.capacity_reference, 2),
        r.status,
        r.first_seen + " / " + r.last_seen,
      ]);
      exportData = records;
    } else if (S.catalogTab === "parameters") {
      headers = [
        "MATRIZ / FILA",
        "REFERENCIA",
        "NOMBRE",
        "EMPRESA",
        "TECNOLOGÍA / Q MÁX.",
        "POTENCIA REF. MW",
      ];
      const records = [
        ...(c.references.plants || []).map((r) => ({
          ...r,
          kind: "Generación",
        })),
        ...(c.references.hydrology || []).map((r) => ({
          ...r,
          kind: "Hidrología",
          source: r["Central_Nombre origen en Consolidado_RDO"],
          plant: r.Nombre_Central_Dashboard,
          company: r.Nombre_Empresa_Dashboard,
          technology: r.Tecnologia,
          capacity_reference: r["Potencia Efectiva (MW)"],
        })),
        ...(c.references.units || []).map((r) => ({
          ...r,
          kind: "URS",
          source: r.urs,
          plant: r.name,
        })),
      ].filter(match);
      rows = records.map((r) => [
        r.matrix_file + " · " + r.matrix_row,
        r.source,
        r.plant,
        r.company,
        r.kind === "Hidrología"
          ? "Qmáx. " + fmt(r["Qturb max"], 3) + " m³/s"
          : r.technology || "URS",
        fmt(r.capacity_reference, 3),
      ]);
      exportData = records;
    } else {
      headers = [
        "FECHA / TIPO",
        "UNIDAD / PARÁMETRO",
        "AVISO",
        "ACCIÓN / CRITERIO",
        "APLICACIÓN",
      ];
      const records = (S.catalogTab === "history" ? c.events : c.alerts)
        .filter(match)
        .slice()
        .sort((a, b) => (b.day || "").localeCompare(a.day || ""));
      rows = records.map((r) => [
        r.day + " · " + r.kind,
        r.asset,
        { html: `<div class="text-wrap">${h(r.message)}</div>` },
        {
          html: `<div class="text-wrap">${h(r.action)}${r.details ? `<small>${h(value(r.details))}</small>` : ""}</div>`,
        },
        {
          html: badge(
            r.automatic ? "Automática" : "Revisión",
            r.severity === "warning" ? "warn" : "info",
          ),
        },
      ]);
      exportData = records;
    }
    return {
      html: `<div class="flow-banner"><span><b>El catálogo se actualiza en cada ejecución.</b> Las unidades nuevas se incorporan al inventario. Un nombre solo se vincula automáticamente cuando coinciden código COES, empresa y referencia inequívoca. Una ausencia o potencia cero no confirman retiro comercial.</span><a class="button secondary small" href="catalogos/revision_actual.json" download>↓ Catálogo y avisos JSON</a></div><section class="stats-grid four">${kpi("Referencias de generación", c.references.plants?.length || 0, "", null, "#A62E78", "Matrices del usuario", "▥", 0)}${kpi("Referencias hidráulicas", c.references.hydrology?.length || 0, "", null, "#3599B8", "Potencia, eficiencia y Qmáx.", "water", 0)}${kpi("URS de la matriz", c.references.units?.length || 0, "", null, "#682888", "Unidad / central y empresa", "▥", 0)}${kpi("Avisos para revisar", c.pending || 0, "", null, "#E86820", "No se inventan parámetros faltantes", "↗", 0)}</section><section class="panel"><div class="panel-head"><div><h2>Fuentes editables del catálogo actual</h2><p>Actualiza estos Excel en catalogos/fuentes y ejecuta actualizar_base.py. Las gráficas históricas usan la revisión vigente para cada fecha.</p></div><span class="badge info">Revisión ${h(c.revision?.slice(0, 12) || "—")}</span></div>${table(
        ["ARCHIVO / HOJA", "TIPO", "FILAS", "SHA-256", "ORIGINAL"],
        c.sources.map((r) => [
          r.file + " · " + r.sheet,
          r.kind,
          r.rows,
          r.sha256.slice(0, 12) + "…",
          {
            html: `<a href="${h(encodeURI("catalogos/fuentes/" + r.sha256 + "/" + r.file))}" download>↓ Matriz original</a>`,
          },
        ]),
        { id: "matrix-sources" },
      )}</section><section class="panel"><div class="panel-head"><div><h2>Revisión de referencias y cambios</h2><p>Inventario de la última fecha archivada: ${h(c.latest_operation_day || "—")}. Las apariciones no determinan fechas de entrada o salida comercial.</p></div></div><div class="panel-controls"><label>Vista <select id="catalog-tab">${tabs.map(([v, t]) => `<option value="${v}" ${S.catalogTab === v ? "selected" : ""}>${t}</option>`).join("")}</select></label><input id="catalog-search" class="search" type="search" value="${h(S.search)}" placeholder="Buscar unidad, matriz o aviso…" aria-label="Buscar catálogo"></div>${table(headers, rows, { id: "catalog-table", limit: 15 })}</section>`,
      after() {
        const keys = [...new Set(exportData.flatMap((r) => Object.keys(r)))];
        exportRows = [
          keys,
          ...exportData.map((r) => keys.map((k) => value(r[k]))),
        ];
      },
    };
  }
  const VIEWS = {
    executive,
    inkia: inkiaView,
    hydro: hydroView,
    thermal: othersView,
    renewable: othersView,
    reserves: reserveView,
    maintenance: maintenanceView,
    electrical: electricalView,
    notes: notesView,
    changes: changesView,
    archive: archiveView,
    catalog: catalogView,
  };
  function filterAvailability() {
    const allowed = {
      hydro: [],
      reserves: ["scope", "company", "period"],
      maintenance: ["scope", "company"],
      electrical: ["period"],
      notes: [],
      archive: [],
      catalog: [],
    }[S.page] || ["scope", "company", "plant", "technology", "period"];
    for (const id of ["scope", "company", "plant", "technology", "period"]) {
      const e = $(id);
      e.disabled = !allowed.includes(id);
      e.title = e.disabled
        ? "Este filtro no aplica a esta sección. Usa sus controles propios."
        : "";
    }
  }
  function updateGlobalFilters() {
    const universe = (active?.series || []).filter(
      (a) =>
        a.generation &&
        (S.scope === "all" || (S.scope === "inkia" ? a.inkia : !a.inkia)),
    );
    setOptions(
      "company",
      [...new Set(universe.map((a) => a.company))].sort(),
      "Todas las empresas",
    );
    setOptions(
      "plant",
      [
        ...new Set(
          universe
            .filter((a) => !S.company || a.company === S.company)
            .map((a) => a.plant),
        ),
      ].sort(),
      "Todas las centrales",
    );
    setOptions(
      "technology",
      [
        ...new Set(
          universe
            .filter(
              (a) =>
                (!S.company || a.company === S.company) &&
                (!S.plant || a.plant === S.plant),
            )
            .map((a) => a.technology)
            .filter(Boolean),
        ),
      ].sort(),
      "Todas las tecnologías",
    );
  }
  function render() {
    for (const c of charts) c.destroy();
    charts = [];
    const vs = current.filter((v) => v.day === S.day);
    active =
      (S.follow ? vs.at(-1) : vs.find((v) => v.code === S.code)) ||
      vs.at(-1) ||
      null;
    S.code = active?.code || "";
    previous = active?.previous
      ? vs.find((v) => v.code === active.previous) || null
      : null;
    updateGlobalFilters();
    filterAvailability();
    $("day").value = S.day;
    $("scope").value = S.scope;
    $("period").value = S.period;
    $("versions").innerHTML = vs
      .map(
        (v, i) =>
          `${i ? '<span class="version-arrow">→</span>' : ""}<button class="version-chip ${v === active ? "selected" : v === previous ? "previous" : ""}" data-code="${h(v.code)}" title="${h(v.filename)}"><i></i>${h(title(v.code))}</button>`,
      )
      .join("");
    $("pair").textContent = active
      ? previous
        ? `${title(S.code)} vs ${title(previous.code)}`
        : S.code === "PDO"
          ? "PDO · programa base"
          : `${title(S.code)} · falta ${title(active.previous)}`
      : "Sin programas archivados";
    $("validity").textContent = active?.publication?.effective_from
      ? "Vigencia desde " + active.publication.effective_from
      : "";
    const run = D.runs.find((r) => r.day === S.day);
    $("run-status").textContent = run?.complete
      ? "Consulta completa"
      : "Consulta parcial";
    $("run-status").className = "badge " + (run?.complete ? "success" : "warn");
    $("checked").textContent = run
      ? "Consultado " + stamp(run.checked_at)
      : "Sin consulta registrada";
    const notices = [
      ...(run?.errors || []),
      ...(run?.normalization_errors || []),
      ...(extra().errors || []),
    ].map((e) => `${e.code}: ${e.message}`);
    if (active?.previous && !previous)
      notices.unshift(
        `Falta ${title(active.previous)}. La comparación exige el predecesor exacto; no se salta a otra emisión.`,
      );
    $("notice").textContent = notices.join("\n");
    $("notice").classList.toggle("hidden", !notices.length);
    const catalog = D.catalog,
      pending = catalog?.pending || 0,
      catalogErrors = catalog?.errors || [];
    $("catalog-banner").classList.toggle(
      "hidden",
      !pending && !catalogErrors.length,
    );
    $("catalog-banner").innerHTML =
      `<div><strong>${pending} avisos de catálogo para revisar</strong><span>Las unidades nuevas se incorporan; los parámetros no confirmados se señalan.${catalogErrors.length ? " " + h(catalogErrors.join(" ")) : ""}</span></div><button class="button secondary small" data-go="catalog">Ver catálogos y alertas ↗</button>`;

    const info = NAV.find((n) => n[0] === S.page);
    $("breadcrumb").textContent = info[1];
    $("page-title").innerHTML = h(info[1]) + "<span>.</span>";
    $("page-description").textContent = info[3];
    for (const b of $("navigation").querySelectorAll("button"))
      b.classList.toggle("active", b.dataset.page === S.page);
    const range = idx();
    $("coverage-note").innerHTML =
      `<span>${active ? `${h(title(S.code))} · ${active.published_intervals} posiciones publicadas` : "Sin datos"}</span><i class="dot"></i><span>Ventana ${D.times[range[0]] || "—"}–${D.times[range.at(-1)] || "—"}</span><i class="dot"></i><span>Clasificación: ${active?.catalog_coverage?.classified || 0}/${active?.catalog_coverage?.total || 0} unidades clasificadas · referencia ${h((active?.reference_revision || D.catalog?.revision || "—").slice(0, 12))}</span>${S.follow ? '<i class="dot"></i><b>Siguiendo la última emisión</b>' : ""}`;
    if (!active) {
      $("content").innerHTML =
        `<section class="panel">${missing("Todavía no hay programas para esta fecha", "Ejecuta actualizar_base.py para consultar el COES y regenerar este HTML.")}</section>`;
      exportRows = [];
    } else {
      const view = VIEWS[S.page]();
      $("content").innerHTML = view.html;
      view.after();
    }
    $("footer-update").textContent = "HTML generado " + stamp(D.generated_at);
    persist();
  }
  function clearFilters() {
    S.hydroFlowScope = "inkia";
    S.reservoirScope = "all";
    S.reservoirCompany = "";
    S.reservoir = "";
    S.scope = "all";
    S.company = "";
    S.plant = "";
    S.technology = "";
    S.period = "common";
    S.search = "";
    S.eventCategory = "";
    S.urs = "";
    S.tables = {};
  }
  function go(page) {
    S.page = page;
    S.tables = {};
    S.search = "";
    render();
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  $("navigation").innerHTML = NAV.map(
    (n, i) =>
      `${i === 9 ? '<div class="nav-separator"></div>' : ""}<button data-page="${n[0]}" aria-label="${h(n[1])}" title="${h(n[1])}">${icon(n[2])}<span>${h(n[1])}</span>${i === 0 ? '<i class="nav-marker"></i>' : ""}</button>`,
  ).join("");
  $("day").innerHTML = days
    .map(
      (d) =>
        `<option value="${d}">${d.split("-").reverse().join("/")}</option>`,
    )
    .join("");
  $("method-content").innerHTML =
    `<p>Se revisaron <strong>9 páginas, 28 tablas y 42 medidas</strong> del PBIX aportado. La identidad visual utiliza su isotipo y su tema magenta. Los datos operativos proceden exclusivamente de las fuentes oficiales de la fecha elegida.</p><h3>Comparación consecutiva</h3><p>PDO → A → B → C → … La ventana común limita los cálculos a las horas publicadas en ambos programas. «Últimos dos publicados» vuelve a seguir automáticamente la emisión más reciente después de regenerar el HTML.</p><h3>Criterios de cálculo y adaptaciones</h3><ul>${(D.report?.methodology || []).map((t) => `<li>${h(t)}</li>`).join("")}</ul><h3>Qué requiere cada sección</h3><p>Despacho y CMg: anexo de operación. Hidrología: anexo 2 diario. RPF: anexos 8A/8B. RSF: anexo 6 o RS_Reprog específico. Intervenciones y análisis eléctrico: anexos 1 y 2 del PDI. Los apuntes se guardan en este navegador.</p><p>Las curvas no incluyen las cifras históricas del PBIX como si fueran datos de hoy. Las capacidades proceden de las matrices editables; los cambios conservan su revisión y los vacíos de las fuentes permanecen sin rellenar.</p>`;
  $("method-button").onclick = () => $("method-dialog").showModal();
  $("close-method").onclick = () => $("method-dialog").close();
  $("method-ok").onclick = () => $("method-dialog").close();
  $("brand-home").onclick = (e) => {
    e.preventDefault();
    go("executive");
  };
  $("refresh-button").onclick = () => {
    persist();
    location.reload();
  };
  $("latest-button").onclick = () => {
    S.follow = true;
    render();
    toast("Se seleccionó la última emisión y su predecesor exacto.");
  };
  $("reset-filters").onclick = () => {
    clearFilters();
    render();
  };
  $("export-page").onclick = () =>
    dataCSV(exportRows, `Kallpa_${S.day}_${S.code}_${S.page}.csv`);
  $("day").onchange = (e) => {
    S.day = e.target.value;
    S.follow = true;
    S.code = "";
    clearFilters();
    render();
  };
  for (const id of ["scope", "company", "plant", "technology", "period"])
    $(id).onchange = (e) => {
      S[id] = e.target.value;
      S.tables = {};
      if (id === "scope") {
        S.company = "";
        S.plant = "";
        S.technology = "";
      }
      if (id === "company") {
        S.plant = "";
        S.technology = "";
      }
      render();
    };
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.page) {
      go(b.dataset.page);
      return;
    }
    if (b.dataset.go) {
      go(b.dataset.go);
      return;
    }
    if (b.dataset.code) {
      S.code = b.dataset.code;
      S.follow = false;
      S.tables = {};
      render();
      return;
    }
    if (b.dataset.reservoir) {
      S.reservoir = b.dataset.reservoir;
      render();
      return;
    }
    if (b.dataset.series) {
      S.series = b.dataset.series;
      render();
      return;
    }
    if (b.dataset.action === "prev") {
      S.tables[b.dataset.table] = Math.max(
        1,
        (S.tables[b.dataset.table] || 1) - 1,
      );
      render();
    }
    if (b.dataset.action === "next") {
      S.tables[b.dataset.table] = (S.tables[b.dataset.table] || 1) + 1;
      render();
    }
    if (b.dataset.action === "export")
      dataCSV(exportRows, `Kallpa_${S.day}_${S.code}_${S.page}.csv`);
    if (b.dataset.action === "export-notes") {
      const note = {
        day: S.day,
        code: S.code,
        digest: active?.digest,
        notes: storedNote(),
        saved_at: new Date().toISOString(),
      };
      downloadBlob(
        new Blob([JSON.stringify(note, null, 2)], { type: "application/json" }),
        `Apuntes_${S.day}_${S.code}.json`,
      );
    }
  });
  document.addEventListener("change", (e) => {
    const id = e.target.id,
      keys = {
        reservoir: "reservoir",
        "hydro-flow-scope": "hydroFlowScope",
        "reservoir-scope": "reservoirScope",
        "reservoir-company": "reservoirCompany",
        "catalog-tab": "catalogTab",
        urs: "urs",
        "event-view": "eventView",
        "event-category": "eventCategory",
        "electrical-page": "electricalPage",
        "change-kind": "changeKind",
        "change-series": "series",
        revisions: "revisions",
      };
    if (keys[id]) {
      S[keys[id]] = id === "revisions" ? e.target.checked : e.target.value;
      S.tables = {};
      render();
    }
    if (id === "threshold") {
      const n = Number(e.target.value);
      if (n > 0 && n <= 100000) {
        S.threshold = n;
        render();
      }
    }
    if (id === "import-notes" && e.target.files[0]) {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result);
          if (typeof data.notes !== "string") throw Error("Formato");
          if (data.day !== S.day || data.code !== S.code)
            throw Error("Los apuntes corresponden a otra fecha o emisión.");
          localStorage.setItem(noteKey(), data.notes);
          render();
          toast("Apuntes importados.");
        } catch (err) {
          toast(err.message || "No se pudieron importar los apuntes.");
        }
      };
      reader.readAsText(e.target.files[0]);
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "notes-text") {
      try {
        localStorage.setItem(noteKey(), e.target.value);
        $("notes-status").textContent =
          "Guardado local · " + new Date().toLocaleTimeString("es-PE");
      } catch (_) {
        $("notes-status").textContent =
          "Este navegador no permite guardar. Exporta los apuntes para conservarlos.";
      }
      return;
    }
    if (
      [
        "event-search",
        "electrical-search",
        "change-search",
        "archive-search",
        "catalog-search",
      ].includes(e.target.id)
    ) {
      const id = e.target.id,
        value = e.target.value,
        pos = e.target.selectionStart;
      S.search = value;
      S.tables = {};
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        render();
        const el = $(id);
        if (el) {
          el.focus();
          el.setSelectionRange(pos, pos);
        }
      }, 220);
    }
  });
  render();
})();
