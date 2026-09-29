$ErrorActionPreference = "Stop"
$Cluster = "meu-lab"

$docker = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Start-Process $docker
}
$ok = $false
foreach ($i in 1..36) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $ok) { throw "Docker nao respondeu" }

$names = @(docker ps -a --filter "label=io.x-k8s.kind.cluster=$Cluster" --format "{{.Names}}")
if ($names.Count -eq 0) { throw "Cluster $Cluster nao existe" }
docker start @names | Out-Null

kubectl config use-context "kind-$Cluster" | Out-Null
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl wait --for=condition=Ready pods --all -n monitoring --timeout=300s

function Start-Tunnel($Svc, $Portas, $Local) {
    $listen = Get-NetTCPConnection -LocalPort $Local -State Listen -ErrorAction SilentlyContinue
    if ($listen) { return }
    $cmd = "while (`$true) { kubectl port-forward -n monitoring svc/$Svc $Portas; Start-Sleep 3 }"
    Start-Process powershell -ArgumentList "-NoExit", "-WindowStyle Minimized", "-Command", $cmd
}
Start-Tunnel "prometheus-grafana" "3000:80" 3000
Start-Tunnel "prometheus-kube-prometheus-prometheus" "9090:9090" 9090
