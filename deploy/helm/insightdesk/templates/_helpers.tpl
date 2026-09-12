{{- define "insightdesk.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "insightdesk.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "insightdesk.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "insightdesk.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "insightdesk.selectorLabels" -}}
app.kubernetes.io/name: {{ include "insightdesk.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "insightdesk.validateSensitiveEnv" -}}
{{- $sensitiveNames := list
  "APP_AUTH_TOKENS_JSON"
  "APP_CONFIG_MASTER_KEY"
  "ARQ_REDIS_DSN"
  "ARQ_REDIS_PASSWORD"
  "ARQ_REDIS_URL"
  "DATABASE_URL"
  "OIDC_CLIENT_SECRET"
  "OPENAI_API_KEY"
  "OPENROUTER_API_KEY"
  "POSTGRES_DSN"
  "POSTGRES_URL"
  "QDRANT_API_KEY"
  "REDIS_URL"
  "SHARE_LINK_SECRET"
  "TAVILY_API_KEY"
-}}
{{- $reservedNames := list
  "ARQ_WORKER_HEARTBEAT_KEY"
  "POD_NAME"
  "TASK_BACKEND"
-}}
{{- range $entry := .Values.env -}}
{{- $name := default "" $entry.name -}}
{{- $sensitiveSuffix := regexMatch "(_API_KEY|_TOKEN|_PASSWORD|_SECRET|_TOKENS_JSON)$" $name -}}
{{- if and (or (has $name $sensitiveNames) $sensitiveSuffix) (hasKey $entry "value") -}}
{{- fail (printf "env[%s].value is forbidden for sensitive settings; use secret.existingSecret or env[].valueFrom.secretKeyRef" $name) -}}
{{- end -}}
{{- if has $name $reservedNames -}}
{{- fail (printf "env[%s] is chart-managed and cannot be overridden through env[]; use the corresponding chart setting instead" $name) -}}
{{- end -}}
{{- end -}}
{{- end -}}
