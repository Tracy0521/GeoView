import importlib.util
import io
import json
import os
import sys
import types
import unittest
from unittest.mock import patch


# Path/configuration helpers do not need a live SSH connection.  A tiny module
# stub keeps this test runnable even before requirements.txt is installed.
paramiko_stub = types.ModuleType('paramiko')
paramiko_stub.SSHClient = object
paramiko_stub.AutoAddPolicy = object
sys.modules.setdefault('paramiko', paramiko_stub)
module_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'applications', 'services', 'remote_models.py')
module_spec = importlib.util.spec_from_file_location('remote_models_under_test', module_path)
remote_models = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(remote_models)


class RemoteModelConfigurationTest(unittest.TestCase):
    def test_reads_numbered_servers_without_exposing_password(self):
        environment = {
            'REMOTE_MODEL_SERVER_1_NAME': '训练机 A',
            'REMOTE_MODEL_SERVER_1_HOST': 'example.test',
            'REMOTE_MODEL_SERVER_1_PORT': '22022',
            'REMOTE_MODEL_SERVER_1_USERNAME': 'root',
            'REMOTE_MODEL_SERVER_1_PASSWORD': 'secret',
            'REMOTE_MODEL_SERVER_1_ROOT': '/root/autodl-tmp'
        }
        with patch.dict(os.environ, environment, clear=True):
            server = remote_models.configured_servers()[0]
        self.assertEqual(server['port'], 22022)
        self.assertNotIn('password', remote_models.public_server(server))

    def test_only_accepts_best_pt_below_output_experiment(self):
        server = {'root': '/root/autodl-tmp'}
        best = '/root/autodl-tmp/output/exp_a/weights/best.pt'
        self.assertEqual(remote_models.validated_model_path(server, best), best)
        self.assertIsNone(remote_models.validated_model_path(
            server, '/root/autodl-tmp/output/exp_a/weights/last.pt'))
        self.assertIsNone(remote_models.validated_model_path(
            server, '/root/autodl-tmp/output/exp_a/weights/../../secret/best.pt'))
        self.assertIsNone(remote_models.validated_model_path(
            server, '/root/autodl-tmp/other/exp_a/weights/best.pt'))

    def test_reads_class_names_from_experiment_dataset(self):
        files = {
            '/root/autodl-tmp/output/exp_a/args.yaml': b'data: /root/autodl-tmp/data/dataset.yaml\n',
            '/root/autodl-tmp/data/dataset.yaml': b'nc: 3\nnames:\n  0: HM\n  1: QHS\n  2: FSC\n'
        }

        class FakeSftp:
            def stat(self, path):
                if path not in files:
                    raise OSError
                return types.SimpleNamespace(st_size=len(files[path]))

            def open(self, path, mode):
                return io.BytesIO(files[path])

        info = remote_models.read_category_info(
            FakeSftp(), {'root': '/root/autodl-tmp'}, '/root/autodl-tmp/output/exp_a')
        self.assertEqual(info['class_names'], ['HM', 'QHS', 'FSC'])
        self.assertEqual(info['class_count'], 3)

    def test_reads_generated_class_metrics_and_validates_dataset_path(self):
        metrics_path = '/root/autodl-tmp/output/exp_a/class_metrics.json'
        files = {metrics_path: json.dumps({'class_metrics': [
            {'class': 'HM', 'ap50': 0.8}, {'class': 'FSC', 'ap50': 0.7}
        ]}).encode('utf-8')}

        class FakeSftp:
            def stat(self, path):
                if path not in files:
                    raise OSError
                return types.SimpleNamespace(st_size=len(files[path]))

            def open(self, path, mode):
                return io.BytesIO(files[path])

        info = remote_models.read_class_metrics(FakeSftp(), '/root/autodl-tmp/output/exp_a')
        self.assertTrue(info['has_class_metrics'])
        self.assertEqual(info['class_metrics_count'], 2)
        server = {'root': '/root/autodl-tmp'}
        self.assertEqual(remote_models.validated_dataset_path(
            server, '/root/autodl-tmp/hrsc/dataset.yaml'),
            '/root/autodl-tmp/hrsc/dataset.yaml')
        self.assertIsNone(remote_models.validated_dataset_path(server, '/etc/passwd'))


if __name__ == '__main__':
    unittest.main()
