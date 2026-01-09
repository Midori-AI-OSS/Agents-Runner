"""Unit tests for agents_runner.log_format module."""

import unittest

from agents_runner.log_format import format_log_line, format_log, wrap_container_log, format_log_display


class TestFormatLogLine(unittest.TestCase):
    """Test cases for format_log_line() function."""
    
    def test_basic_raw_format(self):
        """Test basic raw format output."""
        result = format_log_line("host", "test", "INFO", "hello")
        self.assertEqual(result, "[host/test][INFO] hello")
    
    def test_raw_format_no_padding_inside_brackets(self):
        """Test that raw format has no padding/spaces inside brackets."""
        result = format_log_line("host", "test", "INFO", "message")
        # Should not have spaces like [ host/test    ] or [INFO ]
        self.assertNotIn("[ ", result)
        self.assertNotIn(" ]", result)
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_exactly_one_space_between_header_and_message(self):
        """Test that there is exactly one space between header and message."""
        result = format_log_line("host", "test", "INFO", "message")
        self.assertTrue(result.endswith("] message"))
        self.assertNotIn("]  message", result)  # Not two spaces
        self.assertNotIn("]message", result)    # Not zero spaces
    
    def test_nested_header_stripping(self):
        """Test that nested headers are stripped from message."""
        result = format_log_line("host", "test", "INFO", "[nested/header][WARN] real message")
        self.assertEqual(result, "[host/test][INFO] real message")
    
    def test_multiple_nested_headers_stripped(self):
        """Test that multiple nested headers are all stripped."""
        result = format_log_line("host", "test", "INFO", "[foo/bar][INFO] [baz/qux][WARN] message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_empty_message_after_nested_strip(self):
        """Test that empty messages after nested header strip return empty string."""
        result = format_log_line("host", "test", "INFO", "[nested/header][INFO] ")
        self.assertEqual(result, "")
    
    def test_leading_spaces_preserved_after_header(self):
        """Test that leading spaces in message are preserved after header removal."""
        result = format_log_line("host", "test", "INFO", "  leading spaces")
        self.assertEqual(result, "[host/test][INFO]   leading spaces")
    
    def test_level_normalization_uppercase(self):
        """Test that level names are normalized to uppercase."""
        result = format_log_line("host", "test", "info", "message")
        self.assertEqual(result, "[host/test][INFO] message")
        
        result = format_log_line("host", "test", "warn", "message")
        self.assertEqual(result, "[host/test][WARN] message")
    
    def test_level_normalization_removes_trailing_spaces(self):
        """Test that level names have trailing spaces removed."""
        result = format_log_line("host", "test", "INFO ", "message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_invalid_level_defaults_to_info(self):
        """Test that invalid level names default to INFO."""
        result = format_log_line("host", "test", "INVALID", "message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_padded_format(self):
        """Test padded format for UI display."""
        result = format_log_line("host", "test", "INFO", "message", padded=True)
        # Should have padding inside brackets for alignment
        self.assertIn("[ ", result)
        self.assertIn(" ]", result)
        # Default scope_width is 20
        self.assertTrue(result.startswith("[ host/test"))
    
    def test_padded_format_with_custom_widths(self):
        """Test padded format with custom column widths."""
        result = format_log_line("host", "test", "INFO", "message", 
                                padded=True, scope_width=30, level_width=7)
        self.assertIn("[ host/test", result)
        # With level_width=7, we get "[INFO   ]" (INFO + 3 spaces)
        self.assertIn("][INFO   ] message", result)
    
    def test_long_scope_truncation(self):
        """Test that long scope names are truncated with ellipsis."""
        long_scope = "verylongscope"
        long_subscope = "verylongsubscope"
        result = format_log_line(long_scope, long_subscope, "INFO", "message", 
                                padded=True, scope_width=20)
        # Should be truncated with "..."
        self.assertIn("...", result)
        # Total width should still be approximately scope_width
        scope_part = result.split("][")[0] + "]"
        # Allow some flexibility in exact length due to formatting
        self.assertLessEqual(len(scope_part), 22)  # scope_width + brackets
    
    def test_empty_message(self):
        """Test handling of empty message."""
        result = format_log_line("host", "test", "INFO", "")
        self.assertEqual(result, "")
    
    def test_message_with_brackets_preserved(self):
        """Test that brackets in the message body are preserved."""
        result = format_log_line("host", "test", "INFO", "this [has] brackets")
        self.assertEqual(result, "[host/test][INFO] this [has] brackets")
    
    def test_default_subscope(self):
        """Test that default subscope is 'none'."""
        result = format_log_line("host", level="INFO", message="message")
        self.assertEqual(result, "[host/none][INFO] message")
    
    def test_default_level(self):
        """Test that default level is INFO."""
        result = format_log_line("host", "test", message="message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_special_characters_in_message(self):
        """Test that special characters in message are preserved."""
        result = format_log_line("host", "test", "INFO", "message with $VAR and 'quotes'")
        self.assertEqual(result, "[host/test][INFO] message with $VAR and 'quotes'")


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of refactored functions."""
    
    def test_format_log_unchanged(self):
        """Test that format_log() still works as before."""
        result = format_log("host", "test", "INFO", "message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_wrap_container_log_unchanged(self):
        """Test that wrap_container_log() still works as before."""
        result = wrap_container_log("6e9f1234", "stdout", "container output")
        self.assertEqual(result, "[6e9f/stdout][INFO] container output")
        
        result = wrap_container_log("abcd5678", "stderr", "error message")
        self.assertEqual(result, "[abcd/stderr][WARN] error message")
    
    def test_wrap_container_log_skips_canonical(self):
        """Test that wrap_container_log() skips already-canonical lines."""
        canonical_line = "[host/test][INFO] already formatted"
        result = wrap_container_log("6e9f1234", "stdout", canonical_line)
        self.assertEqual(result, canonical_line)
    
    def test_format_log_display_padded(self):
        """Test that format_log_display() produces padded output."""
        result = format_log_display("[host/test][INFO] message")
        self.assertIn("[ ", result)
        self.assertIn(" ]", result)
        self.assertIn("message", result)


class TestNestedHeaderEdgeCases(unittest.TestCase):
    """Test edge cases for nested header stripping."""
    
    def test_nested_header_with_extra_spaces(self):
        """Test nested header with extra spaces is stripped."""
        # The regex strips the header and one trailing space after it
        result = format_log_line("host", "test", "INFO", "[nested/header][INFO]  message with spaces")
        # One space is stripped with the header, one remains
        self.assertEqual(result, "[host/test][INFO]  message with spaces")
    
    def test_nested_header_no_trailing_space(self):
        """Test nested header without trailing space."""
        result = format_log_line("host", "test", "INFO", "[nested/header][INFO]message")
        self.assertEqual(result, "[host/test][INFO] message")
    
    def test_partial_nested_header_not_stripped(self):
        """Test that partial nested headers are not stripped."""
        result = format_log_line("host", "test", "INFO", "message [not/a][HEADER]")
        self.assertEqual(result, "[host/test][INFO] message [not/a][HEADER]")
    
    def test_nested_header_at_end_of_message(self):
        """Test nested header at end of message."""
        result = format_log_line("host", "test", "INFO", "message [nested/header][INFO]")
        # Should only strip headers at the beginning
        self.assertEqual(result, "[host/test][INFO] message [nested/header][INFO]")


class TestContainerLogFormatting(unittest.TestCase):
    """Test container-specific log formatting scenarios."""
    
    def test_container_id_truncation(self):
        """Test that container ID is truncated to first 4 chars."""
        result = wrap_container_log("6e9f1234567890", "stdout", "message")
        self.assertTrue(result.startswith("[6e9f/"))
    
    def test_short_container_id(self):
        """Test handling of container ID shorter than 4 chars."""
        result = wrap_container_log("abc", "stdout", "message")
        self.assertTrue(result.startswith("[abc/"))
    
    def test_stderr_defaults_to_warn(self):
        """Test that stderr stream defaults to WARN level."""
        result = wrap_container_log("6e9f", "stderr", "error")
        self.assertIn("[WARN]", result)
    
    def test_stdout_defaults_to_info(self):
        """Test that stdout stream defaults to INFO level."""
        result = wrap_container_log("6e9f", "stdout", "message")
        self.assertIn("[INFO]", result)


class TestAcceptanceScenarios(unittest.TestCase):
    """Test acceptance scenarios from the audit."""
    
    def test_scenario_empty_after_nested_strip(self):
        """Acceptance: Empty message after nested header strip."""
        result = format_log_line("host", "clone", "INFO", "[host/clone][INFO] ")
        self.assertEqual(result, "")
    
    def test_scenario_leading_spaces_after_header(self):
        """Acceptance: Message with leading spaces preserved after header."""
        result = format_log_line("host", "clone", "INFO", "  spaces preserved")
        self.assertEqual(result, "[host/clone][INFO]   spaces preserved")
    
    def test_scenario_nested_duplication_removal(self):
        """Acceptance: Nested header duplication removal."""
        result = format_log_line("host", "git", "INFO", "[host/git][INFO] actual message")
        self.assertEqual(result, "[host/git][INFO] actual message")
    
    def test_scenario_tight_format_no_padding(self):
        """Acceptance: Tight format with no padding in brackets."""
        result = format_log_line("desktop", "vnc", "INFO", "Starting Xvnc")
        self.assertEqual(result, "[desktop/vnc][INFO] Starting Xvnc")
        self.assertNotIn("[ desktop", result)
        self.assertNotIn("[INFO ]", result)


if __name__ == "__main__":
    unittest.main()
