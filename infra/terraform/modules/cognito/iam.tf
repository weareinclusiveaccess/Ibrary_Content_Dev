# Attach this policy to the reviewer API task role (ECS / App Runner / Lambda).
data "aws_iam_policy_document" "cognito_admin_api" {
  statement {
    sid    = "CognitoUserAdmin"
    effect = "Allow"
    actions = [
      "cognito-idp:AdminCreateUser",
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminRemoveUserFromGroup",
      "cognito-idp:AdminGetUser",
      "cognito-idp:AdminDisableUser",
      "cognito-idp:AdminEnableUser",
      "cognito-idp:AdminResetUserPassword",
      "cognito-idp:AdminListGroupsForUser",
      "cognito-idp:ListUsers",
      "cognito-idp:ListUsersInGroup",
    ]
    resources = [aws_cognito_user_pool.reviewers.arn]
  }
}

resource "aws_iam_policy" "cognito_admin_api" {
  count = var.create_admin_iam_policy ? 1 : 0

  name        = "${var.project_name}-${var.environment}-review-cognito-admin"
  description = "Allow reviewer portal API to manage Cognito users in the reviewers pool"
  policy      = data.aws_iam_policy_document.cognito_admin_api.json
}
