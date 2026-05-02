
css = open('static/css/style.css', 'r', encoding='utf-8').read()

# 1. Sidebar dark gradient
css = css.replace(
    'background: var(--surface);\n  border-right: 1px solid var(--border);\n  display: flex; flex-direction: column;\n  position: fixed; top: 0; left: 0; bottom: 0;\n  z-index: 100;\n}',
    'background: linear-gradient(180deg, #0b1830 0%, #060e1d 100%);\n  border-right: 1px solid rgba(255,255,255,0.05);\n  display: flex; flex-direction: column;\n  position: fixed; top: 0; left: 0; bottom: 0;\n  z-index: 100;\n}'
)

# 2. Active nav: remove border, add left bar via extra class rule appended
css = css.replace(
    '.nav-item.active {\n  background: var(--gold-dim); color: var(--gold);\n  border: 1px solid rgba(245,158,11,0.18);\n  box-shadow: 0 2px 8px rgba(245,158,11,0.08);\n}',
    '.nav-item.active {\n  background: rgba(245,158,11,0.09); color: var(--gold);\n  font-weight: 600; box-shadow: inset 0 0 0 1px rgba(245,158,11,0.12);\n}'
)

# 3. Frosted topbar
css = css.replace(
    'background: var(--surface); position: sticky; top: 0; z-index: 50;\n}',
    'background: rgba(6,13,30,0.82); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);\n  position: sticky; top: 0; z-index: 50;\n}'
)

# 4. Stat cards gradient
css = css.replace(
    '  background: var(--surface); border: 1px solid var(--border);\n  border-radius: var(--radius); padding: 22px 24px;\n  display: flex; flex-direction: column; gap: 4px;\n  transition: all var(--transition);\n}',
    '  background: linear-gradient(145deg, var(--surface-2), var(--surface));\n  border: 1px solid var(--border);\n  border-radius: var(--radius); padding: 22px 24px;\n  display: flex; flex-direction: column; gap: 4px;\n  transition: all 0.3s ease;\n}'
)

# 5. Table hover
css = css.replace(
    'tbody tr:hover { background: rgba(245,158,11,0.03); }',
    'tbody tr:hover { background: rgba(255,255,255,0.02); }'
)

# 6. Sidebar width
css = css.replace('--sidebar-w:   250px;', '--sidebar-w:   260px;')

# 7. Brand icon more premium
css = css.replace(
    '  box-shadow: 0 4px 12px rgba(245,158,11,0.25);\n}',
    '  box-shadow: 0 4px 20px rgba(245,158,11,0.4), inset 0 1px 0 rgba(255,255,255,0.2);\n}'
)

# 8. Nav label subtler
css = css.replace(
    '  font-size: 0.6rem; font-weight: 700; color: var(--text-muted);\n  letter-spacing: 1.2px; text-transform: uppercase; padding: 14px 10px 6px;\n}',
    '  font-size: 0.55rem; font-weight: 800; color: rgba(255,255,255,0.18);\n  letter-spacing: 2px; text-transform: uppercase; padding: 18px 10px 6px;\n}'
)

# 9. Body bg slightly deeper
css = css.replace('--bg:          #050e1f;', '--bg:          #040c1c;')

open('static/css/style.css', 'w', encoding='utf-8').write(css)
print('OK')
