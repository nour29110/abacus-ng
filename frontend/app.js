const expr = document.getElementById("expr");
const result = document.getElementById("result");
const error = document.getElementById("error");
const tree = document.getElementById("tree");

let timer;
expr.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(calc, 120); });

async function calc() {
  const text = expr.value.trim();
  if (!text) {
    result.textContent = "\u2014";
    error.hidden = true;
    tree.innerHTML = "";
    return;
  }
  try {
    const res = await fetch("/api/calc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expression: text }),
    });
    if (!res.ok) {
      const body = await res.json();
      throw new Error(body.detail || "error");
    }
    const data = await res.json();
    result.textContent = formatNumber(data.result);
    error.hidden = true;
    drawTree(data.ast);
  } catch (e) {
    error.textContent = e.message;
    error.hidden = false;
  }
}

function formatNumber(n) {
  if (Number.isInteger(n)) return n.toString();
  return Number(n.toFixed(10)).toString();
}

function layout(node, depth) {
  if (depth === undefined) depth = 0;
  if (node.type === "num") {
    return { label: String(node.value), width: 1, depth: depth, children: [] };
  }
  if (node.type === "neg") {
    var c = layout(node.child, depth + 1);
    return { label: "-(unary)", width: c.width, depth: depth, children: [c] };
  }
  var l = layout(node.left, depth + 1);
  var r = layout(node.right, depth + 1);
  return { label: node.op, width: l.width + r.width, depth: depth, children: [l, r] };
}

function assignX(node, xStart, unit) {
  if (node.children.length === 0) {
    node.x = xStart + unit / 2;
    return;
  }
  var offset = xStart;
  for (var i = 0; i < node.children.length; i++) {
    assignX(node.children[i], offset, unit);
    offset += node.children[i].width * unit;
  }
  node.x = (node.children[0].x + node.children[node.children.length - 1].x) / 2;
}

function maxDepth(node) {
  var d = node.depth;
  for (var i = 0; i < node.children.length; i++) {
    var cd = maxDepth(node.children[i]);
    if (cd > d) d = cd;
  }
  return d;
}

function setY(node, yStep) {
  node.y = 40 + node.depth * yStep;
  for (var i = 0; i < node.children.length; i++) setY(node.children[i], yStep);
}

function drawTree(ast) {
  var root = layout(ast);
  var W = tree.clientWidth;
  var H = tree.clientHeight;
  var unit = W / root.width;
  assignX(root, 0, unit);
  var md = maxDepth(root);
  var yStep = md === 0 ? 0 : Math.min(90, (H - 60) / md);
  setY(root, yStep);

  var links = "";
  var nodes = "";
  var stack = [root];
  while (stack.length) {
    var n = stack.pop();
    for (var i = 0; i < n.children.length; i++) {
      var c = n.children[i];
      var my = (n.y + c.y) / 2;
      links += '<path class="link" d="M' + n.x + "," + n.y +
        " C" + n.x + "," + my + " " + c.x + "," + my + " " + c.x + "," + c.y + '"/>';
      stack.push(c);
    }
    nodes += '<g class="node" transform="translate(' + n.x + "," + n.y + ')">' +
      '<circle r="22"/><text dy="5">' + escapeXml(n.label) + "</text></g>";
  }
  tree.innerHTML = links + nodes;
}

function escapeXml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/'/g, "&apos;").replace(/"/g, "&quot;");
}
