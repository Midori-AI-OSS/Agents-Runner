# Artifacts Tab Preview Enhancement

## Overview
Enhanced the Artifacts tab preview functionality in `agents_runner/ui/pages/artifacts_tab.py` to provide inline rendering of text files and common image formats, improving user experience by reducing the need to open external applications for quick content viewing.

## Changes Implemented

### 1. Added Text Preview Widget
- **Location**: `__init__` method, line 115-119
- **Widget**: `QPlainTextEdit` configured as read-only
- **Features**:
  - Line wrapping enabled for better readability
  - Maximum 5000 blocks to prevent performance issues with very large files
  - Hidden by default, shown only when text content is selected
  - Added to preview layout with stretch factor for proper sizing

### 2. Enhanced Selection Logic
- **Location**: `_on_selection_changed` method, line 315-370
- **Improvements**:
  - Reset all preview widgets before showing new content
  - Intelligent MIME type detection for content routing
  - Three preview modes:
    1. **Text files** (`text/*`): Inline text preview with syntax preserved
    2. **Images** (`image/png`, `image/jpeg`, `image/jpg`, `image/webp`): Thumbnail preview
    3. **Other files**: Display file info and rely on Open button
  - Size information displayed for non-previewable files
  - Works for both staging (live) and encrypted (archived) artifacts

### 3. Added Text Loading Methods

#### `_load_staging_text` (line 415-435)
- Loads text content directly from staging artifacts
- Implements 1MB file size limit to prevent performance issues
- Uses UTF-8 encoding with error replacement for robust handling
- Shows error messages gracefully if loading fails

#### `_load_encrypted_text` (line 437-475)
- Decrypts and loads text from encrypted artifacts
- Implements same 1MB size limit as staging
- Creates temporary files for decryption (properly tracked for cleanup)
- Handles decryption failures with clear error messages

### 4. Image Preview Refinement
- **Supported formats**: PNG, JPEG, JPG, WEBP
- **Existing logic preserved**: Uses `_load_staging_thumbnail` and `_load_thumbnail`
- **Behavior**: Shows scaled thumbnails (max 400x400) while maintaining aspect ratio

## Technical Details

### File Size Limits
- Text previews: 1MB maximum
- Larger files show a message directing users to use the Open button
- Uses existing `_format_size` helper for human-readable size display

### Error Handling
- All preview loading wrapped in try-catch blocks
- Errors logged and displayed to user with context
- Graceful fallback to preview label for error states

### Widget Visibility Management
- Preview widgets properly hidden/shown based on content type
- Preview label serves as status/error message area
- Text preview widget takes available space with stretch factor

### Compatibility
- Works seamlessly with existing artifact encryption system
- Maintains compatibility with file watcher for live artifacts
- Preserves all existing Open, Edit, and Download button functionality

## Benefits
1. **Improved UX**: Users can quickly view text and image content without opening external applications
2. **Performance**: File size limits prevent UI slowdowns with large files
3. **Safety**: Read-only text widget prevents accidental modifications
4. **Flexibility**: Open button remains available as fallback for all file types
5. **Consistency**: Same preview experience for both staging and archived artifacts

## Testing Recommendations
1. Test with various text file types (plain text, JSON, Python, etc.)
2. Verify image preview for supported formats
3. Test file size limit handling (files > 1MB)
4. Verify encrypted artifact decryption and preview
5. Check error handling with corrupted/invalid files
6. Ensure preview widgets properly reset when switching between artifacts
