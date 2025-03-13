const { override } = require("customize-cra");

module.exports = override((config) => {
  if (config.devServer) {
    config.devServer.client.overlay = false; // 禁用错误覆盖层
  }
  config.watchOptions = {
    ignored: /node_modules/
  };
  return config;
});