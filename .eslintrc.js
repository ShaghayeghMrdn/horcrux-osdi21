module.exports = {
  'env': {
    'browser': true,
    'es2021': true,
    'node': true,
  },
  'extends': [
    'google',
  ],
  'parserOptions': {
    'ecmaVersion': 12,
  },
  'rules': {
    'indent': ['error', 4],
    'require-jsdoc': ['error', {
        'require': {
            'FunctionDeclaration': true,
            'MethodDefinition': false,
            'ClassDeclaration': false,
            'ArrowFunctionExpression': false,
            'FunctionExpression': false
        }
    }]
  },
};
