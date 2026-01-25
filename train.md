# Resume from last checkpoint
python src/train.py --config config/config.yaml --resume models/last_checkpoint.pth

# Or resume from best model
python src/train.py --config config/config.yaml --resume models/best_model.pth


1) test rbac with multitenancy all apis working perfectly with including login, test image predictions both batch and single predictions and  then predict with explainability with heatmap saved and then doctor labelling model predicted images correctly and then merge them for retraining to know whether retraining is working properly or not .i want this full testing end to end with latest model saved in models folder 

2) next after everything above working as expected , then migrate to azure postgresql and all the local storage to azure blob storage and test everything above in step 1 end to end with data stored in blob and push it to "feature/azurev4" branch.

3) after step 2 is stable and working as expected next i need to deploy it in app azure services and give end point url to frontend guy.

python -m uvicorn api.main:app --host 0.0.0.0 --port 8000


