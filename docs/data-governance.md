# Data governance
1. No image enters training without an explicit usage decision.
2. API availability does not itself imply model-training permission.
3. Persist provenance, license, author/owner where available, retrieval date, checksums and perceptual hashes.
4. User uploads are private by default and never become training data merely because they were submitted.
5. Challenge images and labels remain isolated. Failed challenge images are never copied into reference/training data.
6. Suspected duplicates/crops are quarantined for review.
