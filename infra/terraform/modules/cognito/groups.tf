# Role groups: precedence 1 = highest (admin wins if user were in both — avoid dual membership).
resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.reviewers.id
  description  = "Portal administrators — publish units, view LLM judge, manage users"
  precedence   = 1
}

resource "aws_cognito_user_group" "reviewer" {
  name         = "reviewer"
  user_pool_id = aws_cognito_user_pool.reviewers.id
  description  = "Content reviewers — human rubric only, no LLM judge"
  precedence   = 2
}
