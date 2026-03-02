import { describe, it, expect, vi } from 'vitest';
import { 
  formatBytes, 
  formatUptime, 
  formatDate, 
  getFileIcon, 
  escapeHtml, 
  isBinaryFile,
  debounce,
  throttle,
  FILE_ICONS
} from '../js/utils.module.js';

describe('utils.module.js', () => {
  describe('formatBytes', () => {
    it('should format bytes correctly', () => {
      expect(formatBytes(0)).toBe('0 B');
      expect(formatBytes(1024)).toBe('1 KB');
      expect(formatBytes(1024 * 1024)).toBe('1 MB');
      expect(formatBytes(1024 * 1024 * 1024)).toBe('1 GB');
    });

    it('should handle edge cases', () => {
      expect(formatBytes(-1)).toBe('0 B');
      expect(formatBytes(null)).toBe('0 B');
      expect(formatBytes(undefined)).toBe('0 B');
    });

    it('should format with 2 decimal places', () => {
      expect(formatBytes(1536)).toBe('1.5 KB');
      expect(formatBytes(2048)).toBe('2 KB');
    });
  });

  describe('formatUptime', () => {
    it('should format days correctly', () => {
      expect(formatUptime(86400)).toBe('1天 0小时');
      expect(formatUptime(90000)).toBe('1天 1小时');
    });

    it('should format hours correctly', () => {
      expect(formatUptime(3600)).toBe('1小时 0分钟');
      expect(formatUptime(3660)).toBe('1小时 1分钟');
    });

    it('should format minutes correctly', () => {
      expect(formatUptime(60)).toBe('1分钟');
      expect(formatUptime(120)).toBe('2分钟');
    });

    it('should handle edge cases', () => {
      expect(formatUptime(0)).toBe('0分钟');
      expect(formatUptime(-1)).toBe('0分钟');
      expect(formatUptime(null)).toBe('0分钟');
    });
  });

  describe('formatDate', () => {
    it('should format timestamp correctly', () => {
      const timestamp = 1609459200; // 2021-01-01 00:00:00 UTC
      const result = formatDate(timestamp);
      expect(result).not.toBe('--');
      expect(typeof result).toBe('string');
    });

    it('should handle invalid timestamps', () => {
      expect(formatDate(0)).toBe('--');
      expect(formatDate(null)).toBe('--');
      expect(formatDate(undefined)).toBe('--');
    });
  });

  describe('getFileIcon', () => {
    it('should return correct icons for known extensions', () => {
      expect(getFileIcon('test.txt')).toBe('📄');
      expect(getFileIcon('script.js')).toBe('📜');
      expect(getFileIcon('style.css')).toBe('🎨');
      expect(getFileIcon('image.png')).toBe('🖼️');
      expect(getFileIcon('doc.pdf')).toBe('📕');
    });

    it('should return default icon for unknown extensions', () => {
      expect(getFileIcon('unknown.xyz')).toBe('📄');
      expect(getFileIcon('noextension')).toBe('📄');
    });

    it('should handle edge cases', () => {
      expect(getFileIcon('')).toBe('📄');
      expect(getFileIcon(null)).toBe('📄');
      expect(getFileIcon('.htaccess')).toBe('📄');
    });
  });

  describe('escapeHtml', () => {
    it('should escape HTML special characters', () => {
      expect(escapeHtml('<script>alert("xss")</script>')).toContain('&lt;');
      expect(escapeHtml('test & test')).toContain('&amp;');
    });

    it('should handle empty strings', () => {
      expect(escapeHtml('')).toBe('');
      expect(escapeHtml(null)).toBe('');
    });
  });

  describe('isBinaryFile', () => {
    it('should detect binary files', () => {
      const binaryBytes = new Uint8Array([0x00, 0x01, 0x02, 0x03, 0xFF]);
      expect(isBinaryFile(binaryBytes)).toBe(true);
    });

    it('should detect text files', () => {
      const textBytes = new Uint8Array([72, 101, 108, 108, 111]); // "Hello"
      expect(isBinaryFile(textBytes)).toBe(false);
    });

    it('should handle edge cases', () => {
      expect(isBinaryFile(null)).toBe(false);
      expect(isBinaryFile(new Uint8Array())).toBe(false);
    });
  });

  describe('debounce', () => {
    it('should debounce function calls', async () => {
      let count = 0;
      const fn = () => count++;
      const debounced = debounce(fn, 100);
      
      debounced();
      debounced();
      debounced();
      
      expect(count).toBe(0);
      await new Promise(resolve => setTimeout(resolve, 150));
      expect(count).toBe(1);
    });
  });

  describe('throttle', () => {
    it('should throttle function calls', async () => {
      let count = 0;
      const fn = () => count++;
      const throttled = throttle(fn, 100);
      
      throttled();
      throttled();
      throttled();
      
      expect(count).toBe(1);
      await new Promise(resolve => setTimeout(resolve, 150));
      throttled();
      expect(count).toBe(2);
    });
  });

  describe('FILE_ICONS', () => {
    it('should contain common file types', () => {
      expect(FILE_ICONS).toHaveProperty('txt');
      expect(FILE_ICONS).toHaveProperty('js');
      expect(FILE_ICONS).toHaveProperty('html');
      expect(FILE_ICONS).toHaveProperty('css');
      expect(FILE_ICONS).toHaveProperty('json');
    });
  });
});
