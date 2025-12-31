/**
 * Image upload, compression, and preview handling
 */

/**
 * Compress an image file to base64 string
 * @param {File} file - Image file to compress
 * @returns {Promise<string>} Base64 encoded image data (without data URL prefix)
 */
async function compressImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const maxSize = CONFIG.IMAGE.MAX_SIZE;
        let { width, height } = img;
        
        if (width > height && width > maxSize) {
          height *= maxSize / width;
          width = maxSize;
        } else if (height > maxSize) {
          width *= maxSize / height;
          height = maxSize;
        }
        
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        
        if (!ctx) return reject(new Error('Canvas not supported'));
        
        ctx.drawImage(img, 0, 0, width, height);
        
        // Store data URL for display
        AppState.imageDataUrl = canvas.toDataURL('image/jpeg', CONFIG.IMAGE.JPEG_QUALITY);
        
        canvas.toBlob(
          (blob) => {
            if (!blob) return reject(new Error('Compression failed'));
            const fr = new FileReader();
            fr.onloadend = () => {
              const dataUrl = (fr.result || '').toString();
              const [, base64 = ''] = dataUrl.split(',');
              resolve(base64);
            };
            fr.onerror = reject;
            fr.readAsDataURL(blob);
          },
          'image/jpeg',
          CONFIG.IMAGE.BLOB_QUALITY
        );
      };
      img.onerror = () => reject(new Error('Could not read image'));
      img.src = event.target?.result?.toString() || '';
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Format file size in human-readable format
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Initialize image upload handlers
 * @param {Object} elements - DOM elements for image handling
 */
function initImageHandlers(elements) {
  const { uploadInput, uploadBtn, previewThumb, previewName, previewSize, 
          imagePreview, previewRemove, queryImage, queryImagePlaceholder, 
          resultsState } = elements;
  
  // Upload button click
  uploadBtn.addEventListener('click', () => uploadInput.click());
  
  // File input change
  uploadInput.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
      alert('Please choose an image file.');
      return;
    }
    
    try {
      AppState.compressedImage = await compressImage(file);
      
      // Show preview in initial state
      previewThumb.src = AppState.imageDataUrl;
      previewName.textContent = file.name;
      previewSize.textContent = formatFileSize(file.size);
      imagePreview.classList.add('visible');
      uploadBtn.classList.add('has-image');
      
      // Update results state if visible
      if (resultsState.classList.contains('active')) {
        queryImage.src = AppState.imageDataUrl;
        queryImage.classList.remove('hidden');
        queryImagePlaceholder.classList.add('hidden');
      }
    } catch (err) {
      console.error(err);
      alert('Failed to process image. Try a different one.');
    }
  });
  
  // Remove image button
  previewRemove.addEventListener('click', () => {
    AppState.resetImage();
    uploadInput.value = '';
    imagePreview.classList.remove('visible');
    uploadBtn.classList.remove('has-image');
    
    if (resultsState.classList.contains('active')) {
      queryImage.classList.add('hidden');
      queryImagePlaceholder.classList.remove('hidden');
    }
  });
}

/**
 * Trigger upload from results state
 */
function triggerUploadInResults() {
  document.getElementById('upload-input').click();
}
