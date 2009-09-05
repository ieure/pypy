from pypy.rpython.lltypesystem import lltype
from pypy.jit.backend.llsupport import symbolic
from pypy.jit.metainterp.history import AbstractDescr, getkind, BoxInt, BoxPtr
from pypy.jit.metainterp.history import TreeLoop
from pypy.jit.metainterp.resoperation import ResOperation, rop

# The point of the class organization in this file is to make instances
# as compact as possible.  This is done by not storing the field size or
# the 'is_pointer_field' flag in the instance itself but in the class
# (in methods actually) using a few classes instead of just one.


class GcCache(object):
    def __init__(self, translate_support_code):
        self.translate_support_code = translate_support_code
        self._cache_size = {}
        self._cache_field = {}
        self._cache_array = {}
        self._cache_call = {}

    def init_size_descr(self, STRUCT, sizedescr):
        pass

    def init_array_descr(self, ARRAY, arraydescr):
        pass


# ____________________________________________________________
# SizeDescrs

class SizeDescr(AbstractDescr):
    size = 0      # help translation

    def __init__(self, size):
        self.size = size

    def repr_of_descr(self):
        return '<SizeDescr %s>' % self.size

BaseSizeDescr = SizeDescr

def get_size_descr(gccache, STRUCT):
    cache = gccache._cache_size
    try:
        return cache[STRUCT]
    except KeyError:
        size = symbolic.get_size(STRUCT, gccache.translate_support_code)
        sizedescr = SizeDescr(size)
        gccache.init_size_descr(STRUCT, sizedescr)
        cache[STRUCT] = sizedescr
        return sizedescr


# ____________________________________________________________
# FieldDescrs

class BaseFieldDescr(AbstractDescr):
    offset = 0      # help translation
    _clsname = ''

    def __init__(self, offset):
        self.offset = offset

    def sort_key(self):
        return self.offset

    def get_field_size(self, translate_support_code):
        raise NotImplementedError

    def is_pointer_field(self):
        return False        # unless overridden by GcPtrFieldDescr

    def repr_of_descr(self):
        return '<%s %s>' % (self._clsname, self.offset)


class NonGcPtrFieldDescr(BaseFieldDescr):
    _clsname = 'NonGcPtrFieldDescr'
    def get_field_size(self, translate_support_code):
        return symbolic.get_size_of_ptr(translate_support_code)

class GcPtrFieldDescr(NonGcPtrFieldDescr):
    _clsname = 'GcPtrFieldDescr'
    def is_pointer_field(self):
        return True

def getFieldDescrClass(TYPE):
    return getDescrClass(TYPE, BaseFieldDescr, GcPtrFieldDescr,
                         NonGcPtrFieldDescr, 'Field', 'get_field_size')

def get_field_descr(gccache, STRUCT, fieldname):
    cache = gccache._cache_field
    try:
        return cache[STRUCT][fieldname]
    except KeyError:
        offset, _ = symbolic.get_field_token(STRUCT, fieldname,
                                             gccache.translate_support_code)
        FIELDTYPE = getattr(STRUCT, fieldname)
        fielddescr = getFieldDescrClass(FIELDTYPE)(offset)
        cachedict = cache.setdefault(STRUCT, {})
        cachedict[fieldname] = fielddescr
        return fielddescr


# ____________________________________________________________
# ArrayDescrs

_A = lltype.GcArray(lltype.Signed)     # a random gcarray


class BaseArrayDescr(AbstractDescr):
    _clsname = ''

    def get_base_size(self, translate_support_code):
        basesize, _, _ = symbolic.get_array_token(_A, translate_support_code)
        return basesize

    def get_ofs_length(self, translate_support_code):
        _, _, ofslength = symbolic.get_array_token(_A, translate_support_code)
        return ofslength

    def get_item_size(self, translate_support_code):
        raise NotImplementedError

    def is_array_of_pointers(self):
        return False        # unless overridden by GcPtrArrayDescr

    def repr_of_descr(self):
        return '<%s>' % self._clsname


class NonGcPtrArrayDescr(BaseArrayDescr):
    _clsname = 'NonGcPtrArrayDescr'
    def get_item_size(self, translate_support_code):
        return symbolic.get_size_of_ptr(translate_support_code)

class GcPtrArrayDescr(NonGcPtrArrayDescr):
    _clsname = 'GcPtrArrayDescr'
    def is_array_of_pointers(self):
        return True

def getArrayDescrClass(ARRAY):
    return getDescrClass(ARRAY.OF, BaseArrayDescr, GcPtrArrayDescr,
                         NonGcPtrArrayDescr, 'Array', 'get_item_size')

def get_array_descr(gccache, ARRAY):
    cache = gccache._cache_array
    try:
        return cache[ARRAY]
    except KeyError:
        arraydescr = getArrayDescrClass(ARRAY)()
        # verify basic assumption that all arrays' basesize and ofslength
        # are equal
        basesize, itemsize, ofslength = symbolic.get_array_token(ARRAY, False)
        assert basesize == arraydescr.get_base_size(False)
        assert itemsize == arraydescr.get_item_size(False)
        assert ofslength == arraydescr.get_ofs_length(False)
        gccache.init_array_descr(ARRAY, arraydescr)
        cache[ARRAY] = arraydescr
        return arraydescr


# ____________________________________________________________
# CallDescrs

class BaseCallDescr(AbstractDescr):
    _clsname = ''
    call_loop = None
    arg_classes = ''     # <-- annotation hack

    def __init__(self, arg_classes):
        self.arg_classes = arg_classes    # string of "r" and "i" (ref/int)

    def instantiate_arg_classes(self):
        result = []
        for c in self.arg_classes:
            if c == 'i': box = BoxInt()
            else:        box = BoxPtr()
            result.append(box)
        return result

    def returns_a_pointer(self):
        return False         # unless overridden by GcPtrCallDescr

    def get_result_size(self, translate_support_code):
        raise NotImplementedError

    def get_loop_for_call(self, cpu):
        if self.call_loop is not None:
            return self.call_loop
        args = [BoxInt()] + self.instantiate_arg_classes()
        if self.get_result_size(cpu.translate_support_code) == 0:
            result = None
            result_list = []
        else:
            if self.returns_a_pointer():
                result = BoxPtr()
            else:
                result = BoxInt()
            result_list = [result]
        operations = [
            ResOperation(rop.CALL, args, result, self),
            ResOperation(rop.GUARD_NO_EXCEPTION, [], None),
            ResOperation(rop.FAIL, result_list, None)]
        operations[1].suboperations = [ResOperation(rop.FAIL, [], None)]
        loop = TreeLoop('call')
        loop.inputargs = args
        loop.operations = operations
        cpu.compile_operations(loop)
        self.call_loop = loop
        return loop

    def repr_of_descr(self):
        return '<%s>' % self._clsname


class NonGcPtrCallDescr(BaseCallDescr):
    _clsname = 'NonGcPtrCallDescr'
    def get_result_size(self, translate_support_code):
        return symbolic.get_size_of_ptr(translate_support_code)

class GcPtrCallDescr(NonGcPtrCallDescr):
    _clsname = 'GcPtrCallDescr'
    def returns_a_pointer(self):
        return True

class VoidCallDescr(NonGcPtrCallDescr):
    _clsname = 'VoidCallDescr'
    def get_result_size(self, translate_support_code):
        return 0

def getCallDescrClass(RESULT):
    if RESULT is lltype.Void:
        return VoidCallDescr
    return getDescrClass(RESULT, BaseCallDescr, GcPtrCallDescr,
                         NonGcPtrCallDescr, 'Call', 'get_result_size')

def get_call_descr(gccache, ARGS, RESULT):
    arg_classes = []
    for ARG in ARGS:
        kind = getkind(ARG)
        if   kind == 'int': arg_classes.append('i')
        elif kind == 'ref': arg_classes.append('r')
        else:
            raise NotImplementedError('ARG = %r' % (ARG,))
    arg_classes = ''.join(arg_classes)
    cls = getCallDescrClass(RESULT)
    key = (cls, arg_classes)
    cache = gccache._cache_call
    try:
        return cache[key]
    except KeyError:
        calldescr = cls(arg_classes)
        cache[key] = calldescr
        return calldescr


# ____________________________________________________________

def getDescrClass(TYPE, BaseDescr, GcPtrDescr, NonGcPtrDescr,
                  nameprefix, methodname, _cache={}):
    if isinstance(TYPE, lltype.Ptr):
        if TYPE.TO._gckind == 'gc':
            return GcPtrDescr
        else:
            return NonGcPtrDescr
    try:
        return _cache[nameprefix, TYPE]
    except KeyError:
        #
        class Descr(BaseDescr):
            _clsname = '%s%sDescr' % (TYPE._name, nameprefix)
        Descr.__name__ = Descr._clsname
        #
        def method(self, translate_support_code):
            return symbolic.get_size(TYPE, translate_support_code)
        setattr(Descr, methodname, method)
        #
        _cache[nameprefix, TYPE] = Descr
        return Descr