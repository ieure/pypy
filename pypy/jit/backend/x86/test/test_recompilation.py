
from pypy.jit.backend.x86.runner import CPU
from pypy.jit.backend.x86.test.test_regalloc import BaseTestRegalloc

class TestRecompilation(BaseTestRegalloc):
    def test_compile_bridge_not_deeper(self):
        ops = '''
        [i0]
        i1 = int_add(i0, 1)
        i2 = int_lt(i1, 20)
        guard_true(i2)
           fail(i1)
        jump(i1)
        '''
        loop = self.interpret(ops, [0])
        assert self.getint(0) == 20
        ops = '''
        [i1]
        i3 = int_add(i1, 1)
        fail(i3)
        '''
        bridge = self.attach_bridge(ops, loop, loop.operations[-2])
        self.cpu.set_future_value_int(0, 0)
        op = self.cpu.execute_operations(loop)
        assert op is bridge.operations[-1]
        assert self.getint(0) == 21
    
    def test_compile_bridge_deeper(self):
        ops = '''
        [i0]
        i1 = int_add(i0, 1)
        i2 = int_lt(i1, 20)
        guard_true(i2)
           fail(i1)
        jump(i1)
        '''
        loop = self.interpret(ops, [0])
        previous = loop._x86_stack_depth
        assert self.getint(0) == 20
        ops = '''
        [i1]
        i3 = int_add(i1, 1)
        i4 = int_add(i3, 1)
        i5 = int_add(i4, 1)
        i6 = int_add(i5, 1)
        i7 = int_add(i5, i4)
        i8 = int_add(i7, 1)
        i9 = int_add(i8, 1)
        fail(i3, i4, i5, i6, i7, i8, i9)
        '''
        bridge = self.attach_bridge(ops, loop, loop.operations[-2])
        new = loop.operations[2]._x86_bridge_stack_depth
        assert new > previous
        self.cpu.set_future_value_int(0, 0)
        op = self.cpu.execute_operations(loop)
        assert op is bridge.operations[-1]
        assert self.getint(0) == 21
        assert self.getint(1) == 22
        assert self.getint(2) == 23
        assert self.getint(3) == 24

    def test_bridge_jump_to_other_loop(self):
        loop = self.interpret('''
        [i0, i10, i11, i12, i13, i14, i15, i16]
        i1 = int_add(i0, 1)
        i2 = int_lt(i1, 20)
        guard_true(i2)
           fail(i1)
        jump(i1, i10, i11, i12, i13, i14, i15, i16)
        ''', [0])
        other_loop = self.interpret('''
        [i3]
        guard_false(i3)
           fail(i3)
        jump(i3)
        ''', [1])
        ops = '''
        [i3]
        jump(i3, 1, 2, 3, 4, 5, 6, 7)
        '''
        bridge = self.attach_bridge(ops, other_loop, other_loop.operations[0],
                                    jump_targets=[loop])
        self.cpu.set_future_value_int(0, 1)
        op = self.cpu.execute_operations(other_loop)
        assert op is loop.operations[2].suboperations[0]

    def test_bridge_jumps_to_self_deeper(self):
        loop = self.interpret('''
        [i0, i1, i2, i31, i32, i33]
        i30 = int_add(i1, i2)
        i3 = int_add(i0, 1)
        i4 = int_and(i3, 1)
        guard_false(i4)
            fail(0, i3)
        i5 = int_lt(i3, 20)
        guard_true(i5)
            fail(1, i3)
        jump(i3, i30, 1, i30, i30, i30)
        ''', [0])
        assert self.getint(0) == 0
        assert self.getint(1) == 1
        ops = '''
        [i3]
        i10 = int_mul(i3, 2)
        i8 = int_add(i3, 1)
        i6 = int_add(i8, i10)
        i7 = int_add(i3, i6)
        i12 = int_add(i7, i8)
        i11 = int_add(i12, i6)
        jump(i3, i12, i11, i10, i6, i7)
        '''
        guard_op = loop.operations[3]
        bridge = self.attach_bridge(ops, loop, guard_op,
                                    jump_targets=[loop])
        assert guard_op._x86_bridge_stack_depth > loop._x86_stack_depth
        self.cpu.set_future_value_int(0, 0)
        self.cpu.set_future_value_int(1, 0)
        self.cpu.set_future_value_int(2, 0)
        self.cpu.execute_operations(loop)
        assert self.getint(0) == 1
        assert self.getint(1) == 20

    def test_bridge_jumps_to_self_shallower(self):
        loop = self.interpret('''
        [i0, i1, i2]
        i3 = int_add(i0, 1)
        i4 = int_and(i3, 1)
        guard_false(i4)
            fail(0, i3)
        i5 = int_lt(i3, 20)
        guard_true(i5)
            fail(1, i3)
        jump(i3, i1, i2)
        ''', [0])
        assert self.getint(0) == 0
        assert self.getint(1) == 1
        ops = '''
        [i3]
        jump(i3, 0, 1)
        '''
        bridge = self.attach_bridge(ops, loop, loop.operations[2],
                                    jump_targets=[loop])
        self.cpu.set_future_value_int(0, 0)
        self.cpu.set_future_value_int(1, 0)
        self.cpu.set_future_value_int(2, 0)
        self.cpu.execute_operations(loop)
        assert self.getint(0) == 1
        assert self.getint(1) == 20
        