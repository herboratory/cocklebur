# 持久化存儲與備份還原 (Storage & Backup)

本文件說明 Cocklebur Server 的持久化儲存架構、PVC 設定原則、以及資料庫備份與災難還原手冊。

---

## 1. 持久化存儲架構

### 1.1 掛載點與資料目錄結構
Cocklebur Server 將所有狀態保存在容器內的 `/data` 目錄：
```text
/data/
├── cocklebur.db        # 主 SQLite 關聯資料庫
├── .host_key           # 系統自動生成之 Bootstrap Key (若未透過環境變數指定)
├── uploads/            # 使用者上傳之附件檔案
└── packs/              # 專案匯出與匯入的封存封裝包
```

### 1.2 PVC 規格標準
- **存取模式 (Access Mode)**：`ReadWriteOnce` (RWO)。
- **容量配額 (Capacity)**：
  - 開發 / 測試 / 預發環境：預設 `10Gi`。
  - 生產環境：建議至少 `20Gi`（可根據實際附件使用量向上擴展）。
- **儲存類別 (StorageClass)**：
  - **ENG / UAT**：`microk8s-hostpath`（單節點本機高速存儲）。
  - **STG**：`nfs-csi`（網路共用儲存）。
  - **PROD**：雲端供應商高可靠區塊存儲（如 AWS `ebs-csi`、GCP `pd-csi`、Ceph RBD）。

---

## 2. 權限與檔案鎖定維護 (fsGroup)

由於底層為 SQLite 資料庫，在容器以非 Root 使用者（UID 10001）執行時，必須確保兩點：
1. **目錄寫入權限**：PVC 掛載進容器時，Kubelet 會依據 `securityContext.fsGroup: 10001` 自動賦予群組 10001 讀寫權限。
2. **避免多節點並行掛載**：嚴禁使用 `ReadWriteMany` 將同一個 PVC 掛載至多個並行執行的 Pod，否則可能發生 SQLite 讀寫衝突或鎖死。

---

## 3. 線上資料備份程序 (Backup Procedures)

### 方式 A：透過 Kubectl 進行檔案級備份 (推薦)

在不停機的情況下，直接透過容器內部工具打包 `/data` 目錄：

```bash
POD_NAME=$(kubectl get pod -n cocklebur-app -l app.kubernetes.io/name=cocklebur-server -o jsonpath='{.items[0].metadata.name}')
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="cocklebur_backup_${TIMESTAMP}.tar.gz"

echo "正在將 /data 目錄封裝為 ${BACKUP_FILENAME}..."
kubectl exec -n cocklebur-app "$POD_NAME" -- tar -czf "/tmp/${BACKUP_FILENAME}" -C /data .

echo "正在下載備份檔案至本機..."
kubectl cp "cocklebur-app/${POD_NAME}:/tmp/${BACKUP_FILENAME}" "./${BACKUP_FILENAME}"

echo "清除容器內暫存檔..."
kubectl exec -n cocklebur-app "$POD_NAME" -- rm -f "/tmp/${BACKUP_FILENAME}"

echo "備份完成！本機檔案: ./${BACKUP_FILENAME}"
```

### 方式 B：Kubernetes VolumeSnapshot (若叢集支援 CSI 快照)
若叢集安裝有 `snapshot.storage.k8s.io`，可建立 `VolumeSnapshot` 資源：
```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: cocklebur-snapshot
  namespace: cocklebur-app
spec:
  volumeSnapshotClassName: csi-hostpath-snapclass
  source:
    persistentVolumeClaimName: cocklebur-data
```

---

## 4. 災難還原程序 (Restore Procedures)

若資料庫損毀或需還原至先前的備份狀態，請依循以下安全程序：

### 步驟 1：暫停應用程式以釋放檔案鎖定
將 Deployment 的副本數縮容為 0：
```bash
kubectl scale deployment/cocklebur-server -n cocklebur-app --replicas=0
```

### 步驟 2：啟動維護用輔助 Pod 掛載 PVC
建立一個臨時 Pod 掛載 `cocklebur-data` PVC：
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: cocklebur-restore-helper
  namespace: cocklebur-app
spec:
  securityContext:
    runAsUser: 10001
    fsGroup: 10001
  containers:
    - name: helper
      image: busybox:latest
      command: ["sleep", "3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: cocklebur-data
EOF
```
等待 Pod 啟動完成：
```bash
kubectl wait --for=condition=Ready pod/cocklebur-restore-helper -n cocklebur-app --timeout=60s
```

### 步驟 3：清空舊資料並還原備份包
```bash
# 上傳備份壓縮檔至輔助 Pod
kubectl cp "./cocklebur_backup_latest.tar.gz" "cocklebur-app/cocklebur-restore-helper:/tmp/restore.tar.gz"

# 解壓縮並覆蓋至 /data
kubectl exec -it cocklebur-restore-helper -n cocklebur-app -- rm -rf /data/*
kubectl exec -it cocklebur-restore-helper -n cocklebur-app -- tar -xzf /tmp/restore.tar.gz -C /data
```

### 步驟 4：清理維護 Pod 並恢復應用程式
```bash
# 刪除臨時輔助 Pod
kubectl delete pod cocklebur-restore-helper -n cocklebur-app

# 恢復應用程式 Pod
kubectl scale deployment/cocklebur-server -n cocklebur-app --replicas=1

# 驗證 Rollout
kubectl rollout status deployment/cocklebur-server -n cocklebur-app
```

---

## 5. 清理與重設實例 (Clean Reset Warning)

> [!CAUTION]
> **刪除 PVC 將永久刪除所有專案、卡片、留言與使用者資料！**
> 一旦刪除 PVC，重建後系統將視為全新安裝，既有的 Bootstrap Key 與所有 Host Recovery Code 將全部失效，必須重新經歷 Claim Host 流程。
```bash
# 警告：此操作不可逆！
kubectl delete pvc cocklebur-data -n cocklebur-app
```
