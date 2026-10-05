"""Corporate ownership, package constraints and no false-green release gates."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import openai_plugin as package

class PipelineTests(unittest.TestCase):
    def test_only_exact_probe_destinations_allowed(self):
        for url in ('http://elbowsupknivesout.warreandvavasour.com',
                    package.ORIGIN+'.evil.test', package.ORIGIN+'/other',
                    package.ORIGIN+'?query=1', package.ORIGIN+'#fragment',
                    'https://user:pass@elbowsupknivesout.warreandvavasour.com',
                    'https://other-service.a.run.app', 'https://127.0.0.1'):
            with self.subTest(url=url), patch.object(package,'build_opener') as opener:
                with self.assertRaises(ValueError): package.probe(url)
                opener.assert_not_called()

    def test_backend_failure_is_nonzero(self):
        report={'backend_checks_pass':False,'technical_checks_pass':False}
        with patch.object(package,'probe',return_value=report), patch('sys.argv',['builder','probe','--require-backend']):
            self.assertEqual(package.main(),1)

    def test_missing_portal_gates_do_not_imply_backend_failure(self):
        report={'backend_checks_pass':True,'technical_checks_pass':False}
        with patch.object(package,'probe',return_value=report), patch('sys.argv',['builder','probe','--require-backend']):
            self.assertEqual(package.main(),0)
        with patch.object(package,'probe',return_value=report), patch('sys.argv',['builder','probe','--require-ready']):
            self.assertEqual(package.main(),1)

    def test_corporate_ownership_and_manual_deploy_are_preserved(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/'.github/workflows/deploy-cloud-run.yml').read_text()
        self.assertIn("github.repository == 'WarreAndVavasour/WorkspaceAlberta'",workflow)
        self.assertIn("github.repository_id == '1400771945'",workflow)
        self.assertIn("github.repository_owner_id == '323728381'",workflow)
        self.assertNotIn('HarleyCoops/WorkspaceAlberta',workflow)
        self.assertNotIn('  push:',workflow)
        self.assertIn('workflow_dispatch:',workflow)
        manifest=json.loads((package.PACKAGE/'plugin.json').read_text())
        self.assertEqual(manifest['repository'],'https://github.com/WarreAndVavasour/WorkspaceAlberta')
        review=manifest['extensions']['com.openai']['review']['test_cases']
        self.assertEqual(len(review['positive']),5)
        self.assertEqual(len(review['negative']),3)

    def test_publisher_prefix_spoofing_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'plugin'
            shutil.copytree(package.PACKAGE,root)
            path=root/'plugin.json'
            data=json.loads(path.read_text())
            data['extensions']['com.openai']['interface']['websiteURL']=package.ORIGIN+'.evil.test'
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):package.validate(root)

if __name__=='__main__':unittest.main()
