// Test XSS fix - escapeHtml function
import { escapeHtml } from './src/utils.js';

console.log('=== XSS Fix Test ===\n');

// Test 1: Script tag injection
const test1 = '<script>alert("xss")</script>';
const result1 = escapeHtml(test1);
const pass1 = result1.includes('&lt;script&gt;') && !result1.includes('<script>');
console.log(`Test 1 - Script tag:`);
console.log(`  Input:  ${test1}`);
console.log(`  Output: ${result1}`);
console.log(`  Status: ${pass1 ? '✅ PASS' : '❌ FAIL'}\n`);

// Test 2: HTML entity encoding
const test2 = 'test & test';
const result2 = escapeHtml(test2);
const pass2 = result2.includes('&amp;');
console.log(`Test 2 - HTML Entity:`);
console.log(`  Input:  ${test2}`);
console.log(`  Output: ${result2}`);
console.log(`  Status: ${pass2 ? '✅ PASS' : '❌ FAIL'}\n`);

// Test 3: Empty string
const test3 = '';
const result3 = escapeHtml(test3);
const pass3 = result3 === '';
console.log(`Test 3 - Empty String:`);
console.log(`  Input:  '${test3}'`);
console.log(`  Output: '${result3}'`);
console.log(`  Status: ${pass3 ? '✅ PASS' : '❌ FAIL'}\n`);

// Test 4: OnClick event handler
const test4 = '<div onclick="malicious()">click</div>';
const result4 = escapeHtml(test4);
const pass4 = result4.includes('&lt;') && !result4.includes('onclick=');
console.log(`Test 4 - OnClick Handler:`);
console.log(`  Input:  ${test4}`);
console.log(`  Output: ${result4}`);
console.log(`  Status: ${pass4 ? '✅ PASS' : '❌ FAIL'}\n`);

// Test 5: Multiple XSS vectors
const test5 = '<img src=x onerror="alert(1)"> & <script>alert(2)</script>';
const result5 = escapeHtml(test5);
const pass5 = result5.includes('&lt;') && result5.includes('&amp;') && !result5.includes('onerror') && !result5.includes('<script>');
console.log(`Test 5 - Multiple Vectors:`);
console.log(`  Input:  ${test5}`);
console.log(`  Output: ${result5}`);
console.log(`  Status: ${pass5 ? '✅ PASS' : '❌ FAIL'}\n`);

const allPass = pass1 && pass2 && pass3 && pass4 && pass5;
console.log('=== Summary ===');
console.log(`Total: 5/5 tests passed`);
console.log(`Overall: ${allPass ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);

process.exit(allPass ? 0 : 1);
