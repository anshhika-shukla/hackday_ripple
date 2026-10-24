# Initialize git repository and create milestone commit for RIPPLE
Write-Host "Initializing Git repository..." -ForegroundColor Cyan
git init
git config user.name "RIPPLE Team"
git config user.email "ripple@example.com"
git add .
git commit -m "feat: complete RIPPLE phases 0-7 (offline impact analysis & test selection agent)"
git tag mvp
Write-Host "✅ Git repository initialized, committed, and tagged 'mvp'!" -ForegroundColor Green
