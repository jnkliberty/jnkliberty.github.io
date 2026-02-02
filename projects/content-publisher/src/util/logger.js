const winston = require('winston');

// Define log levels for different processes
const logLevels = {
  extracting: process.env.LOG_EXTRACTING_LEVEL || 'error',
  publishing: process.env.LOG_PUBLISHING_LEVEL || 'info',
  worker: process.env.LOG_WORKER_LEVEL || 'error'
};

// Define log file paths
const logFilePaths = {
  extracting: './logs/extracting-errors.log',
  publishing: './logs/publishing-errors.log',
  worker: './logs/worker-errors.log'
};

// Create separate loggers for each process
const loggers = {

  extracting: winston.createLogger({
    level: logLevels.extracting,
    format: winston.format.combine(
      winston.format.label({ label: '[EXTRACT]' }),
      winston.format.timestamp(),
      winston.format.printf(({ level, message, label, timestamp }) => {
        let formattedMessage = typeof message === 'object'
          ? JSON.stringify(message, null, 2)
          : message;
        return `${timestamp} ${label} ${level}: ${formattedMessage}`;
      })
    ),
    transports: [
      new winston.transports.Console(),
      new winston.transports.File({
        filename: logFilePaths.extracting,
        level: 'error'
      })
    ]
  }),

  publishing: winston.createLogger({
    level: logLevels.publishing,
    format: winston.format.combine(
      winston.format.label({ label: '[PUBLISH]' }),
      winston.format.timestamp(),
      winston.format.printf(({ level, message, label, timestamp }) => {
        let formattedMessage = typeof message === 'object'
          ? JSON.stringify(message, null, 2)
          : message;
        return `${timestamp} ${label} ${level}: ${formattedMessage}`;
      })
    ),
    transports: [
      new winston.transports.Console(),
      new winston.transports.File({
        filename: logFilePaths.publishing,
        level: 'error'
      })
    ]
  }),

  worker: winston.createLogger({
    level: logLevels.worker,
    format: winston.format.combine(
      winston.format.label({ label: '[WORKER]' }),
      winston.format.timestamp(),
      winston.format.printf(({ level, message, label, timestamp }) => {
        let formattedMessage = typeof message === 'object'
          ? JSON.stringify(message, null, 2)
          : message;
        return `${timestamp} ${label} ${level}: ${formattedMessage}`;
      })
    ),
    transports: [
      new winston.transports.Console(),
      new winston.transports.File({
        filename: logFilePaths.worker,
        level: 'error'
      })
    ]
  })

};

module.exports = { loggers };
