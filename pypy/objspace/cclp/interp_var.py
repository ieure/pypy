from pypy.objspace.cclp.variable import wait__Var, _assign_aliases, _entail
from pypy.objspace.cclp.types import W_Var, W_CVar
from pypy.objspace.cclp.global_state import scheduler
from pypy.objspace.cclp.misc import w


def interp_free(w_var):
    return isinstance(w_var.w_bound_to, W_Var)

def interp_wait(space, obj):
    return wait__Var(space, obj)


class RebindingError(Exception): pass

def interp_bind(w_var, obj):
    if interp_free(w_var):
        return interp_assign_aliases(w_var, obj)
    if w_var.w_bound_to == obj:
        return
    raise RebindingError

class EntailmentError(Exception): pass

def interp_entail(w_v1, w_v2):
    w_v1val = w_v1.w_bound_to
    w_v2val = w_v2.w_bound_to
    if not interp_free(w_v1):
        if not interp_free(w_v2):
            # let's be simpler than unify
            if w_v1val != w_v2val:
                raise EntailmentError
        return interp_assign_aliases(w_v2, w_v1val)
    else:
        w_v1.entails[w_v2] = True


def interp_assign_aliases(w_var, w_val):
    w("  :assign")
    assert isinstance(w_var, W_Var)
    w_curr = w_var
    while 1:
        w_next = w_curr.w_bound_to
        _assign(w_curr, w_val)
        # notify the blocked threads
        scheduler[0].unblock_on(w_curr)
        if w_next is w_var:
            break
        # switch to next
        w_curr = w_next
    _assign_entailed(w_var, w_val)
    w("  :assigned")

def _assign_entailed(w_var, w_val):
    w("   :assign entailed")
    for var in w_var.entails:
        if interp_free(var):
            interp_assign_aliases(var, w_val)
        else:
            if w_var.w_bound_to != w_val:
                raise EntailmentError

def _assign(w_var, w_val):
    assert isinstance(w_var, W_Var)
    if isinstance(w_var, W_CVar):
        if not w_val in w_var.w_dom._values.content:
            raise ValueError, "assignment out of domain"
    w_var.w_bound_to = w_val
