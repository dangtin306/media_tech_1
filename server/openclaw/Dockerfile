FROM media_tech_ai:latest

WORKDIR /opt/openclaw

RUN npm init -y >/dev/null 2>&1 && npm install ws@8.18.0 --no-package-lock --omit=dev

COPY openclaw.js /workspace/server/openclaw/openclaw.js
COPY config.json /workspace/server/openclaw/config.json
COPY control-ui /workspace/server/openclaw/control-ui

CMD ["node", "openclaw.js"]
