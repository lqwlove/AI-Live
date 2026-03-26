// Node.js wrapper: 接收 MD5 参数，输出签名
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const md5Param = process.argv[2];
if (!md5Param) {
    process.exit(1);
}

const signPath = path.join(__dirname, 'sign.js');
const code = fs.readFileSync(signPath, 'utf-8');

const context = vm.createContext({ global: {}, window: {}, document: {} });
vm.runInContext(code, context);
const result = vm.runInContext(`get_sign("${md5Param}")`, context);
process.stdout.write(result);
