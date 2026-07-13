{{- define "hangar.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "hangar.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "hangar.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "hangar.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | quote }}
app.kubernetes.io/name: {{ include "hangar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: hangar
{{- end -}}

{{- define "hangar.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hangar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/part-of: hangar
{{- end -}}

{{- define "hangar.image" -}}
{{- if .digest -}}
{{- printf "%s@%s" .repository .digest -}}
{{- else -}}
{{- printf "%s:%s" .repository .tag -}}
{{- end -}}
{{- end -}}

{{- define "hangar.publicOrigin" -}}
{{- printf "%s://%s" .Values.publicUrl.scheme .Values.publicUrl.host -}}
{{- end -}}

{{- define "hangar.coreSecretEnv" -}}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.application.name }}
      key: {{ .Values.existingSecrets.application.secretKeyKey }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.database.name }}
      key: {{ .Values.existingSecrets.database.urlKey }}
{{- end -}}

{{- define "hangar.celerySecretEnv" -}}
- name: REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.cache.name }}
      key: {{ .Values.existingSecrets.cache.urlKey }}
- name: AMQP_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.queue.name }}
      key: {{ .Values.existingSecrets.queue.urlKey }}
{{- end -}}

{{- define "hangar.objectStorageSecretEnv" -}}
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.objectStorage.name }}
      key: {{ .Values.existingSecrets.objectStorage.accessKeyIdKey }}
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.existingSecrets.objectStorage.name }}
      key: {{ .Values.existingSecrets.objectStorage.secretAccessKeyKey }}
{{- end -}}

{{- define "hangar.apiSecretEnv" -}}
{{ include "hangar.coreSecretEnv" . }}
{{ include "hangar.celerySecretEnv" . }}
{{ include "hangar.objectStorageSecretEnv" . }}
{{- end -}}

{{- define "hangar.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .gid }}
fsGroup: {{ .gid }}
fsGroupChangePolicy: OnRootMismatch
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "hangar.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .gid }}
capabilities:
  drop:
    - ALL
{{- end -}}

{{- define "hangar.scheduling" -}}
nodeSelector:
{{ toYaml .Values.podDefaults.nodeSelector | indent 2 }}
affinity:
{{ toYaml .Values.podDefaults.affinity | indent 2 }}
tolerations:
{{ toYaml .Values.podDefaults.tolerations | indent 2 }}
topologySpreadConstraints:
{{ toYaml .Values.podDefaults.topologySpreadConstraints | indent 2 }}
{{- end -}}
