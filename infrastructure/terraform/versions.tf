terraform {
  required_version = ">= 1.7"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.80" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # Remote state: configure per environment before first apply.
  # backend "s3" {
  #   bucket         = "orbitalsentinel-tfstate"
  #   key            = "aegis/prod/terraform.tfstate"
  #   region         = "us-gov-west-1"
  #   dynamodb_table = "aegis-tf-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "aegis-missionos"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
