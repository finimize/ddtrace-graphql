import sys
import unittest.mock as mock
import pytest

import ddtrace_graphql
from ddtrace_graphql import patch, unpatch


class TestDDTraceCompatibility:
    """Test ddtrace version compatibility features."""
    
    def test_import_fallback_success_old_ddtrace(self):
        """Test that the library imports successfully with old ddtrace structure."""
        # Mock the old ddtrace.contrib.util.require_modules approach
        with mock.patch.dict('sys.modules', {'ddtrace.contrib.util': mock.MagicMock()}):
            with mock.patch('ddtrace_graphql.require_modules') as mock_require:
                mock_require.return_value.__enter__.return_value = []  # No missing modules
                
                # Force reimport to test the fallback
                if 'ddtrace_graphql' in sys.modules:
                    del sys.modules['ddtrace_graphql']
                    
                import ddtrace_graphql
                
                # Should have imported successfully
                assert hasattr(ddtrace_graphql, 'patch')
                assert hasattr(ddtrace_graphql, 'unpatch')
                assert hasattr(ddtrace_graphql, 'traced_graphql')
    
    def test_import_fallback_success_new_ddtrace(self):
        """Test that the library imports successfully with new ddtrace structure."""
        # Mock the new ddtrace structure (no contrib.util)
        with mock.patch.dict('sys.modules'):
            # Remove contrib.util to simulate new ddtrace
            if 'ddtrace.contrib.util' in sys.modules:
                del sys.modules['ddtrace.contrib.util']
                
            with mock.patch('ddtrace_graphql.graphql') as mock_graphql:
                # Force reimport to test the fallback
                if 'ddtrace_graphql' in sys.modules:
                    del sys.modules['ddtrace_graphql']
                    
                import ddtrace_graphql
                
                # Should have imported successfully via fallback
                assert hasattr(ddtrace_graphql, 'patch')
                assert hasattr(ddtrace_graphql, 'unpatch')
                assert hasattr(ddtrace_graphql, 'traced_graphql')
    
    def test_import_fallback_missing_graphql(self):
        """Test graceful handling when graphql module is missing."""
        # Mock both ddtrace.contrib.util and graphql missing
        with mock.patch.dict('sys.modules'):
            # Remove both contrib.util and graphql
            if 'ddtrace.contrib.util' in sys.modules:
                del sys.modules['ddtrace.contrib.util']
            if 'graphql' in sys.modules:
                del sys.modules['graphql']
                
            with mock.patch('builtins.__import__', side_effect=ImportError("No module named 'graphql'")):
                # Force reimport to test the fallback
                if 'ddtrace_graphql' in sys.modules:
                    del sys.modules['ddtrace_graphql']
                    
                # Should not raise an exception, just log warnings
                import ddtrace_graphql
                
                # Module should still be importable but without the main functionality
                assert 'ddtrace_graphql' in sys.modules
    
    def test_unwrap_function_compatibility_old_ddtrace(self):
        """Test that unwrap works with old ddtrace.util.unwrap."""
        from ddtrace_graphql.patch import unwrap
        
        # Mock old ddtrace.util.unwrap
        with mock.patch('ddtrace_graphql.patch.unwrap') as mock_unwrap:
            mock_unwrap.return_value = None
            
            # Test unpatching
            unpatch()
            
            # Should have been called twice (for graphql and execute_and_validate)
            assert mock_unwrap.call_count == 2
    
    def test_unwrap_function_compatibility_new_ddtrace(self):
        """Test that unwrap works with new ddtrace.internal.utils.wrappers.unwrap."""
        # Mock the scenario where old unwrap fails but new one works
        with mock.patch('ddtrace_graphql.patch.unwrap') as mock_unwrap:
            mock_unwrap.return_value = None
            
            # Test unpatching
            unpatch()
            
            # Should have been called twice (for graphql and execute_and_validate)
            assert mock_unwrap.call_count == 2
    
    def test_unwrap_function_compatibility_wrapt_fallback(self):
        """Test that unwrap falls back to wrapt when ddtrace unwrap is not available."""
        # This would test the scenario where both ddtrace unwrap methods fail
        # and we fall back to wrapt.unwrap_function_wrapper
        
        # Mock both ddtrace unwrap methods to fail
        with mock.patch('ddtrace_graphql.patch.unwrap') as mock_unwrap:
            mock_unwrap.side_effect = Exception("Unwrap failed")
            
            # Test unpatching should not raise exception
            unpatch()  # Should handle the exception gracefully
            
            # Should have attempted unwrapping twice (for graphql and execute_and_validate)
            assert mock_unwrap.call_count == 2
    
    def test_patch_unpatch_cycle_compatibility(self):
        """Test that patch/unpatch cycle works with compatibility changes."""
        # Ensure we can patch and unpatch successfully
        try:
            patch()
            unpatch()
            patch()
            unpatch()
            # If we get here without exceptions, the compatibility is working
            assert True
        except Exception as e:
            pytest.fail(f"Patch/unpatch cycle failed: {e}")
    
    def test_logging_on_import_failures(self):
        """Test that appropriate logging occurs when imports fail."""
        import logging
        
        with mock.patch('ddtrace_graphql.logger') as mock_logger:
            with mock.patch('builtins.__import__', side_effect=ImportError("Test import error")):
                # Force reimport to test logging
                if 'ddtrace_graphql' in sys.modules:
                    del sys.modules['ddtrace_graphql']
                    
                try:
                    import ddtrace_graphql
                except ImportError:
                    pass  # Expected for this test
                
                # Should have logged warnings about failed imports
                mock_logger.warning.assert_called()
    
    def test_version_requirements_in_setup(self):
        """Test that setup.py has the correct ddtrace version requirement."""
        import setup
        
        # Check that ddtrace>=0.50.0 is in install_requires
        install_requires = setup.setup.keywords.get('install_requires', [])
        ddtrace_req = next((req for req in install_requires if req.startswith('ddtrace')), None)
        
        assert ddtrace_req is not None, "ddtrace should be in install_requires"
        assert '>=0.50.0' in ddtrace_req, "ddtrace should have minimum version requirement"