from openalea.mtg import MTG, io

def test_issue16():
    g = MTG(r'data/issue16.mtg', has_date=True)
    roots = g.roots(scale=2)
    assert len(roots)==1, roots


def test1():
    code = '/P/A1/S1<A2'
    symbols = dict(P=1, A=2, S=3)
    #features = None#{'_line': 'INT'}
    g = io.multiscale_edit(code, symbol_at_scale=symbols)

    assert g.max_scale() == 3, g.max_scale()
    assert len(g.roots(scale=2)) == 1
    assert g.parent(4) == 2
    assert g.complex(4) == 1


def test2():
    code = '/P/A1/S1[+A2[+A3]]'
    symbols = dict(P=1, A=2, S=3)
    #features = None#{'_line': 'INT'}
    g = io.multiscale_edit(code, symbol_at_scale=symbols)
    assert len(g.roots(scale=2)) == 1
    assert g.parent(4) == 2
    assert g.parent(5) == 4

def test3():
    code = '/P/A1/S1[+A2<A3/S2]'
    symbols = dict(P=1, A=2, S=3)
    #features = None#{'_line': 'INT'}
    g = io.multiscale_edit(code, symbol_at_scale=symbols)
    assert len(g.roots(scale=2)) == 1
    assert len(g.roots(scale=3)) == 2
    assert g.parent(4) == 2
    assert g.parent(5) == 4

def test4():
    code = '/P/A/B/S<A/B/S'
    symbols = dict(P=1, A=2, B=3, S=4)
    #features = None#{'_line': 'INT'}
    g = io.multiscale_edit(code, symbol_at_scale=symbols)
    assert len(g.roots(scale=2)) == 1
    assert len(g.roots(scale=3)) == 1
    assert len(g.roots(scale=4)) == 1
    assert g.parent(5) == 2
    assert g.parent(6) == 3
    assert g.parent(7) == 4

def test5():
    code = '/P/A/B/S<A<A/B[+A/B<A/B/S]<A[+A/B/S]'
    symbols = dict(P=1, A=2, B=3, S=4)
    #features = None#{'_line': 'INT'}
    g = io.multiscale_edit(code, symbol_at_scale=symbols)
    assert g.roots(1) == [1]
    assert g.roots(2) == [2]
    assert g.roots(3) == [3, 7, 15]
    assert g.roots(4) == [4,12,16]

def test_label():
    code = '/P1.1<P1.2<P1.33'
    symbols = dict(P=1)
    g = io.multiscale_edit(code, symbol_at_scale=symbols)
    assert g.label(1) == 'P1.1'
    assert g.label(2) == 'P1.2'
    assert g.label(3) == 'P1.33'
    assert g.index(1) == '1.1'
    assert g.index(2) == '1.2'
    assert g.index(3) == '1.33'
