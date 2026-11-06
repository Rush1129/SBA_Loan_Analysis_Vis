/* Risk Atlas hover effects for Plotly charts (see DESIGN.md › Hover). Dash loads every
   file in assets/ automatically.

   - Donut slices: the hovered slice thickens in its own colour (no white outline), lifts
     with a soft shadow tinted with its own colour, the other slices fade, and the centre label
     (an annotation named "center") shows that slice's share and count.
   - Map regions (choropleth): the hovered state grows around its own centre and lifts
     with a drop shadow.

   Plotly draws these shapes itself (map paths even have pointer-events: none) and re-applies
   their inline styles when it redraws, so CSS :hover can't drive this. Instead this hooks
   Plotly's own hover events and toggles classes (.sba-lift / .sba-dim) that style.css styles
   with !important. */
(function () {
  "use strict";

  function addClass(el, cls, undo) {
    el.classList.add(cls);
    undo.push(function () { el.classList.remove(cls); });
  }

  function setCenter(gd, index, text) {
    var anns = (gd.layout && gd.layout.annotations) || [];
    if (!window.Plotly || index == null || !anns[index]) return null;
    var upd = {};
    upd["annotations[" + index + "].text"] = text;
    return window.Plotly.relayout(gd, upd);
  }

  function clear(gd) {
    var h = gd._sbaHover;
    gd._sbaHover = null;
    if (!h) return;
    h.undo.forEach(function (fn) { fn(); });
    if (h.center != null) setCenter(gd, h.center, h.centerText);
  }

  function liftSlice(gd, pt, undo) {
    var hit = null;
    var others = [];
    gd.querySelectorAll(".pielayer .trace").forEach(function (t) {
      var cd = t.__data__;
      if (!cd || !cd[0] || !cd[0].trace || cd[0].trace.index !== pt.curveNumber) return;
      t.querySelectorAll(".slice").forEach(function (s) {
        if (s.__data__ && s.__data__.i === pt.pointNumber) hit = s;
        else others.push(s);
      });
    });
    var path = hit && hit.querySelector("path.surface");
    if (!path) return;
    hit.parentNode.appendChild(hit); // draw the lifted slice above its neighbours
    var fill = path.style.fill || pt.color || "rgb(14, 17, 22)";
    path.style.setProperty("--sba-fill", fill);
    path.style.setProperty("--sba-shadow", fill.replace(/^rgb\((.*)\)$/, "rgba($1, 0.5)"));
    addClass(path, "sba-lift", undo);
    others.forEach(function (s) {
      var p = s.querySelector("path.surface");
      if (p) addClass(p, "sba-dim", undo);
    });
  }

  // Plotly redraws the pie after the centre-label relayout (and again when Dash re-renders the
  // graph), re-binding slice data by DOM position. Because the lifted slice is moved to the top,
  // a redraw would repaint it with its neighbour's shape. So the lift is (re)applied by slice
  // data after every redraw instead of being tied to one DOM node.
  function reliftPie(gd) {
    var h = gd._sbaHover;
    if (!h || !h.pie) return;
    h.undo.forEach(function (fn) { fn(); });
    h.undo = [];
    liftSlice(gd, h.pie, h.undo);
  }

  function hoverPie(gd, pt, key) {
    var h = { key: key, undo: [], center: null, pie: pt };
    gd._sbaHover = h;
    var redraw = null;
    var anns = (gd.layout && gd.layout.annotations) || [];
    for (var i = 0; i < anns.length; i++) {
      if (anns[i].name !== "center") continue;
      var total = 0;
      ((pt.fullData || pt.data).values || []).forEach(function (v) { total += Number(v) || 0; });
      var share = pt.percent != null ? pt.percent : (total ? pt.value / total : 0);
      var name = String(pt.label).split(" · ")[0].toLowerCase();
      h.center = i;
      h.centerText = anns[i].text;
      redraw = setCenter(gd, i, "<b>" + (share * 100).toFixed(1) + "%</b><br><span style='font-size:12px;color:#646B78'>" +
        Number(pt.value).toLocaleString("en-US") + " " + name + "</span>");
      break;
    }
    Promise.resolve(redraw).then(function () {
      if (gd._sbaHover === h) reliftPie(gd); // skip if the mouse already moved on
    });
  }

  function hoverMap(gd, pt, key) {
    var hit = null;
    gd.querySelectorAll(".choroplethlayer .trace").forEach(function (t) {
      var cd = t.__data__;
      if (!cd || !cd[0] || !cd[0].trace || cd[0].trace.index !== pt.curveNumber) return;
      t.querySelectorAll("path.choroplethlocation").forEach(function (p) {
        if (p.__data__ && p.__data__.loc === pt.location) hit = p;
      });
    });
    if (!hit) return;
    var undo = [];
    hit.parentNode.appendChild(hit); // the grown state sits above its neighbours
    addClass(hit, "sba-lift", undo);
    gd._sbaHover = { key: key, undo: undo, center: null };
  }

  function onHover(gd, ev) {
    var pt = ev && ev.points && ev.points[0];
    if (!pt) return;
    var type = (pt.fullData || pt.data || {}).type;
    if (type !== "pie" && type !== "choropleth") return;
    var key = type + ":" + pt.curveNumber + ":" + (type === "pie" ? pt.pointNumber : pt.location);
    if (gd._sbaHover && gd._sbaHover.key === key) return;
    clear(gd);
    if (type === "pie") hoverPie(gd, pt, key);
    else hoverMap(gd, pt, key);
  }

  function bind(gd) {
    if (typeof gd.on !== "function" || !gd._ev || gd._sbaEv === gd._ev) return;
    gd._sbaEv = gd._ev; // re-bind if Plotly ever rebuilds the graph's event emitter
    gd.on("plotly_hover", function (ev) { onHover(gd, ev); });
    gd.on("plotly_unhover", function () { clear(gd); });
    gd.on("plotly_afterplot", function () { reliftPie(gd); });
  }

  var queued = false;
  function scan() {
    queued = false;
    document.querySelectorAll(".js-plotly-plot").forEach(bind);
  }
  function queue() {
    if (queued) return;
    queued = true;
    window.setTimeout(scan, 60); // not requestAnimationFrame: it pauses in background tabs
  }
  function start() {
    queue();
    new MutationObserver(queue).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
