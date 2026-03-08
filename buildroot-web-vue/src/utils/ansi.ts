// ANSI 颜色代码辅助函数
// 避免在代码中直接使用 \x1b 转义序列

export const ANSI = {
  // 颜色代码
  RESET: '\x1b[0m',
  BOLD: '\x1b[1m',
  DIM: '\x1b[2m',
  
  // 前景色
  RED: '\x1b[31m',
  GREEN: '\x1b[32m',
  YELLOW: '\x1b[33m',
  BLUE: '\x1b[34m',
  MAGENTA: '\x1b[35m',
  CYAN: '\x1b[36m',
  WHITE: '\x1b[37m',
  
  // 亮色
  BRIGHT_RED: '\x1b[91m',
  BRIGHT_GREEN: '\x1b[92m',
  BRIGHT_YELLOW: '\x1b[93m',
  BRIGHT_BLUE: '\x1b[94m',
  BRIGHT_MAGENTA: '\x1b[95m',
  BRIGHT_CYAN: '\x1b[96m',
  BRIGHT_WHITE: '\x1b[97m',
}

// 便捷函数
export const color = {
  red: (text: string) => `${ANSI.RED}${text}${ANSI.RESET}`,
  green: (text: string) => `${ANSI.GREEN}${text}${ANSI.RESET}`,
  yellow: (text: string) => `${ANSI.YELLOW}${text}${ANSI.RESET}`,
  blue: (text: string) => `${ANSI.BLUE}${text}${ANSI.RESET}`,
  cyan: (text: string) => `${ANSI.CYAN}${text}${ANSI.RESET}`,
  white: (text: string) => `${ANSI.WHITE}${text}${ANSI.RESET}`,
  
  bold: {
    red: (text: string) => `${ANSI.BOLD}${ANSI.RED}${text}${ANSI.RESET}`,
    green: (text: string) => `${ANSI.BOLD}${ANSI.GREEN}${text}${ANSI.RESET}`,
    yellow: (text: string) => `${ANSI.BOLD}${ANSI.YELLOW}${text}${ANSI.RESET}`,
    blue: (text: string) => `${ANSI.BOLD}${ANSI.BLUE}${text}${ANSI.RESET}`,
    cyan: (text: string) => `${ANSI.BOLD}${ANSI.CYAN}${text}${ANSI.RESET}`,
    white: (text: string) => `${ANSI.BOLD}${ANSI.WHITE}${text}${ANSI.RESET}`,
  }
}