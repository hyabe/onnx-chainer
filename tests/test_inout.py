import chainer
import chainer.functions as F
import chainer.links as L
from chainer import testing
import numpy as np

from onnx_chainer.testing import input_generator
from tests.helper import ONNXModelTest


@testing.parameterize(
    {'condition': 'tuple'},
    {'condition': 'tuple_with_name', 'input_names': ['x', 'y', 'z']},
    {'condition': 'list', 'in_type': 'list'},
    {'condition': 'list_with_names', 'in_type': 'list',
     'input_names': ['x', 'y', 'z']},
    {'condition': 'var', 'in_type': 'variable'},
    {'condition': 'var_with_names', 'in_type': 'variable',
     'input_names': ['x', 'y', 'z']},
    {'condition': 'varlist', 'in_type': 'variable_list'},
    {'condition': 'varlist_with_names', 'in_type': 'variable_list',
     'input_names': ['x', 'y', 'z']},
    {'condition': 'dict', 'in_type': 'dict'},
    {'condition': 'dict_with_names', 'in_type': 'dict',
     'input_names': {'x': 'in_x', 'y': 'in_y', 'z': 'in_z'}},
    {'condition': 'dict_with_name_list', 'in_type': 'dict',
     'input_names': ['x', 'y', 'z']},
    {'condition': 'vardict', 'in_type': 'variable_dict'},
    {'condition': 'vardict_with_names', 'in_type': 'variable_dict',
     'input_names': {'x': 'in_x', 'y': 'in_y', 'z': 'in_z'}},
)
class TestMultipleInputs(ONNXModelTest):

    def get_model(self):

        class Model(chainer.Chain):

            def __init__(self):
                super(Model, self).__init__()
                with self.init_scope():
                    self.prelu = L.PReLU()

            def __call__(self, x, y, z):
                return F.relu(x) + self.prelu(y) * z

        return Model()

    def get_x(self, in_type=None):
        base_x = (input_generator.increasing(1, 5),
                  input_generator.increasing(1, 5)*1.1,
                  input_generator.increasing(1, 5)*1.2)
        names = ['x', 'y', 'z']
        if in_type is None:
            return base_x
        elif in_type == 'list':
            return list(base_x)
        elif in_type == 'variable':
            return tuple(chainer.Variable(v) for v in base_x)
        elif in_type == 'variable_list':
            return [chainer.Variable(v) for v in base_x]
        elif in_type == 'dict':
            return {names[i]: v for i, v in enumerate(base_x)}
        elif in_type == 'variable_dict':
            return {names[i]: chainer.Variable(v)
                    for i, v in enumerate(base_x)}

    def test_multiple_inputs(self):
        model = self.get_model()
        x = self.get_x(getattr(self, 'in_type', None))
        name = 'multipleinputs_' + self.condition
        input_names = getattr(self, 'input_names', None)
        self.expect(model, x, name=name, input_names=input_names)


class TestImplicitInput(ONNXModelTest):

    def setUp(self):

        class Model(chainer.Chain):

            def __init__(self):
                super(Model, self).__init__()

                self.frac = chainer.Parameter(np.array(2, dtype=np.float32))

            def __call__(self, x):
                return x / self.frac

        self.model = Model()

    def test_implicit_input(self):
        x = chainer.Variable(np.array(1, dtype=np.float32))
        self.expect(self.model, x)


@testing.parameterize(
    {'use_bn': True, 'out_type': 'dict', 'condition': 'bn_out_dict'},
    {'use_bn': False, 'out_type': 'dict', 'condition': 'out_dict'},
    {'use_bn': True, 'out_type': 'dict', 'condition': 'bn_out_dict_with_name',
     'output_names': {'tanh': 'out_tanh', 'sigmoid': 'out_sigmoid'}},
    {'use_bn': True, 'out_type': 'dict',
     'condition': 'bn_out_dict_with_name_list',
     'output_names': ('out_tanh', 'out_sigmoid')},
    {'use_bn': True, 'out_type': 'tuple', 'condition': 'bn_out_tuple'},
    {'use_bn': True, 'out_type': 'tuple',
     'condition': 'bn_out_tuple_with_name',
     'output_names': ['out_tanh', 'out_sigmoid']},
    {'use_bn': True, 'out_type': 'list', 'condition': 'bn_out_list'},
    {'use_bn': True, 'out_type': 'list', 'condition': 'bn_out_list_with_name',
     'output_names': ['out_tanh', 'out_sigmoid']},
)
class TestMultipleOutput(ONNXModelTest):

    def get_model(self, use_bn=False, out_type=None):
        class Model(chainer.Chain):

            def __init__(self, use_bn=False, out_type=None):
                super(Model, self).__init__()

                self._use_bn = use_bn
                self._out_type = out_type
                with self.init_scope():
                    self.conv = L.Convolution2D(None, 32, ksize=3, stride=1)
                    if self._use_bn:
                        self.bn = L.BatchNormalization(32)

            def __call__(self, x):
                h = self.conv(x)
                if self._use_bn:
                    h = self.bn(h)
                o1 = F.tanh(h)
                o2 = F.sigmoid(h)
                if self._out_type == 'dict':
                    return {
                        'tanh': o1,
                        'sigmoid': o2
                    }
                elif self._out_type == 'tuple':
                    return o1, o2
                elif self._out_type == 'list':
                    return [o1, o2]

        return Model(use_bn=use_bn, out_type=out_type)

    def test_multiple_outputs(self):
        model = self.get_model(use_bn=self.use_bn, out_type=self.out_type)
        x = np.zeros((1, 3, 32, 32), dtype=np.float32)
        name = 'multipleoutput_' + self.condition
        output_names = getattr(self, 'output_names', None)
        self.expect(model, x, name=name, output_names=output_names)


class TestIntermediateOutput(ONNXModelTest):

    def get_model(self):
        class Model(chainer.Chain):

            def __init__(self):
                super().__init__()
                with self.init_scope():
                    self.l1 = L.Linear(4)
                    self.l2 = L.Linear(5, initial_bias=0.1)

            def __call__(self, x):
                y = self.l1(x)
                z = self.l2(y)
                return y, z
        return Model()

    def test_outputs(self):
        model = self.get_model()
        x = np.ones((1, 3), dtype=np.float32)
        self.expect(model, x, output_names=['y', 'z'])
