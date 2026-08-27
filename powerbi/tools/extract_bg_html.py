"""Reconstroi o HTML gerado pelas measures _BG Pagina 1/2 do _Background.tmdl.

O background do dashboard e HTML+CSS emitido por DAX e renderizado pelo visual
HTML Content. Para auditar esse CSS com o detector do Impeccable e preciso
materializa-lo em arquivos .html:

    python3 powerbi/tools/extract_bg_html.py /tmp/bg
    node .claude/skills/impeccable/scripts/detect.mjs /tmp/bg/*.html

Valores dinamicos (FORMAT, measures) viram placeholders — a estrutura e o CSS
sao fieis ao que o Power BI renderiza.
"""
import re, sys, pathlib
SRC = pathlib.Path("powerbi/RFM.SemanticModel/definition/tables/_Background.tmdl")
OUT = pathlib.Path(sys.argv[1])
text = SRC.read_text(encoding="utf-8")

# ---- separa measures -------------------------------------------------------
measures = {}
pat = re.compile(r"^\tmeasure '([^']+)' =\s*(.*?)^\t\tlineageTag:", re.S | re.M)
for m in pat.finditer(text):
    measures[m.group(1)] = m.group(2)


def tokenize(expr):
    """Devolve lista de ('lit', str) | ('id', str) | ('call', None)."""
    out, i, n = [], 0, len(expr)
    while i < n:
        c = expr[i]
        if c == '"':
            buf, i = [], i + 1
            while i < n:
                if expr[i] == '"':
                    if i + 1 < n and expr[i + 1] == '"':
                        buf.append('"'); i += 2; continue
                    i += 1; break
                buf.append(expr[i]); i += 1
            out.append(("lit", "".join(buf)))
            continue
        if c == "/" and expr[i:i + 2] == "//":
            i = expr.find("\n", i)
            if i == -1: break
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in "_."):
                j += 1
            word = expr[i:j]
            k = j
            while k < n and expr[k] in " \t\r\n":
                k += 1
            if k < n and expr[k] == "(":  # chamada de função → consome parênteses
                depth, k2 = 0, k
                while k2 < n:
                    if expr[k2] == '"':
                        k2 += 1
                        while k2 < n:
                            if expr[k2] == '"':
                                if k2 + 1 < n and expr[k2 + 1] == '"':
                                    k2 += 2; continue
                                break
                            k2 += 1
                    elif expr[k2] == "(":
                        depth += 1
                    elif expr[k2] == ")":
                        depth -= 1
                        if depth == 0:
                            k2 += 1; break
                    k2 += 1
                out.append(("call", None)); i = k2; continue
            out.append(("id", word)); i = j; continue
        i += 1
    return out


def parse_measure(body):
    """Extrai {var: expr} e a expressão do RETURN."""
    lines = [ln.rstrip() for ln in body.split("\n")]
    vars_, cur_name, cur_buf, ret_buf, in_ret = {}, None, [], [], False
    for ln in lines:
        s = ln.strip()
        mv = re.match(r"^VAR\s+(\w+)\s*=\s*(.*)$", s)
        if mv and not in_ret:
            if cur_name:
                vars_[cur_name] = "\n".join(cur_buf)
            cur_name, cur_buf = mv.group(1), [mv.group(2)]
            continue
        if re.match(r"^RETURN\b", s) and not in_ret:
            if cur_name:
                vars_[cur_name] = "\n".join(cur_buf)
            cur_name, in_ret = None, True
            ret_buf.append(re.sub(r"^RETURN\s*", "", s))
            continue
        (ret_buf if in_ret else cur_buf).append(ln)
    if cur_name:
        vars_[cur_name] = "\n".join(cur_buf)
    return vars_, "\n".join(ret_buf) if in_ret else "\n".join(cur_buf)


def resolve(expr, vars_, seen=()):
    """Resolve uma expressao DAX em texto, expandindo VARs recursivamente.
    Uma unica passagem: nunca re-tokeniza texto ja desescapado."""
    parts, had_lit = [], False
    for kind, val in tokenize(expr):
        if kind == "lit":
            parts.append(val); had_lit = True
        elif kind == "call":
            parts.append("123")
        elif val in vars_ and val not in seen:
            sub, sub_lit = resolve(vars_[val], vars_, seen + (val,))
            # VAR puramente numerica (sem literal) vira placeholder legivel
            parts.append(sub if sub_lit else "50")
            had_lit = had_lit or sub_lit
    return "".join(parts), had_lit


def render(name):
    vars_, ret = parse_measure(measures[name])
    html, _ = resolve(ret, vars_)
    return re.sub(r"^[ \t]+", "", html, flags=re.M)


OUT.mkdir(parents=True, exist_ok=True)
for label, name in (("pagina-1", "_BG Pagina 1"), ("pagina-2", "_BG Pagina 2")):
    dst = OUT / f"bg-{label}.html"
    dst.write_text(render(name), encoding="utf-8")
    print(f"{dst}  ({dst.stat().st_size} bytes)")
