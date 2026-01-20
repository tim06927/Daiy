"""Tests for recipe format in JobIdentification."""

from web.job_identification import (
    JobIdentification,
    RecipeInstructions,
    UnclearSpecification,
)


class TestRecipeInstructions:
    """Test RecipeInstructions class."""
    
    def test_create_recipe(self):
        """Test creating a recipe with ingredients and steps."""
        ingredients = [
            {"name": "replacement [drivetrain_cassettes]", "type": "part"},
            {"name": "chain [drivetrain_chains]", "type": "part"},
            {"name": "[drivetrain_tools]", "type": "tool"},
        ]
        steps = [
            "Step 1: Shift to smallest chainring",
            "Step 2: Use [drivetrain_tools] to remove the chain",
            "Step 3: Install new chain [drivetrain_chains]",
        ]
        
        recipe = RecipeInstructions(ingredients=ingredients, steps=steps)
        
        assert len(recipe.ingredients) == 3
        assert len(recipe.steps) == 3
        assert recipe.get_ingredient_names() == [
            "replacement [drivetrain_cassettes]",
            "chain [drivetrain_chains]",
            "[drivetrain_tools]",
        ]
    
    def test_recipe_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "cassette [drivetrain_cassettes]", "type": "part"},
                {"name": "wrench [drivetrain_tools]", "type": "tool"},
            ],
            steps=[
                "Remove old cassette using [drivetrain_tools]",
                "Install new [drivetrain_cassettes]",
            ]
        )
        
        # Serialize
        recipe_dict = recipe.to_dict()
        assert "ingredients" in recipe_dict
        assert "steps" in recipe_dict
        
        # Deserialize
        recipe2 = RecipeInstructions.from_dict(recipe_dict)
        assert recipe2.get_ingredient_names() == recipe.get_ingredient_names()
        assert recipe2.steps == recipe.steps
    
    def test_get_referenced_categories(self):
        """Test extracting category keys from ingredients."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "chain [drivetrain_chains]", "type": "part"},
                {"name": "[drivetrain_cassettes]", "type": "part"},
                {"name": "[drivetrain_tools]", "type": "tool"},
            ],
            steps=[],
        )
        
        categories = recipe.get_referenced_categories()
        assert set(categories) == {"drivetrain_chains", "drivetrain_cassettes", "drivetrain_tools"}
    
    def test_validate_recipe_all_ingredients_used(self):
        """Test validation checks that all ingredients are used."""
        # Invalid: cassettes not used in steps
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "cassette [drivetrain_cassettes]", "type": "part"},
                {"name": "chain [drivetrain_chains]", "type": "part"},
            ],
            steps=[
                "Install the chain [drivetrain_chains]",
            ]
        )
        
        is_valid, errors = recipe.validate_recipe()
        assert not is_valid
        assert any("cassette" in error for error in errors)
    
    def test_validate_recipe_valid(self):
        """Test validation passes when recipe is consistent."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "cassette [drivetrain_cassettes]", "type": "part"},
                {"name": "chain [drivetrain_chains]", "type": "part"},
            ],
            steps=[
                "Install the cassette [drivetrain_cassettes]",
                "Install the chain [drivetrain_chains]",
            ]
        )
        
        is_valid, errors = recipe.validate_recipe()
        assert is_valid
        assert len(errors) == 0


class TestJobIdentificationWithRecipe:
    """Test JobIdentification with recipe format."""
    
    def test_job_with_recipe(self):
        """Test JobIdentification using recipe format."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "cassette [drivetrain_cassettes]", "type": "part"},
                {"name": "chain [drivetrain_chains]", "type": "part"},
                {"name": "chain breaker [drivetrain_tools]", "type": "tool"},
            ],
            steps=[
                "Remove the old chain using the chain breaker [drivetrain_tools]",
                "Install the new cassette [drivetrain_cassettes]",
                "Install the new chain [drivetrain_chains]",
            ]
        )
        
        job = JobIdentification(
            recipe=recipe,
            unclear_specifications=[
                UnclearSpecification(
                    spec_name="drivetrain_speed",
                    confidence=0.7,
                    question="How many gears does your bike have?",
                    hint="Count the cogs on the back wheel",
                    options=["8-speed", "9-speed", "10-speed"],
                )
            ],
            confidence=0.9,
            reasoning="User needs to replace drivetrain",
        )
        
        assert job.recipe == recipe
        assert len(job.unclear_specifications) == 1
        assert job.referenced_categories == ["drivetrain_cassettes", "drivetrain_chains", "drivetrain_tools"]
    
    def test_job_to_dict_with_recipe(self):
        """Test serialization with recipe format."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "cassette [drivetrain_cassettes]", "type": "part"},
            ],
            steps=["Install cassette [drivetrain_cassettes]"],
        )
        
        job = JobIdentification(
            recipe=recipe,
            unclear_specifications=[],
            confidence=0.8,
            reasoning="Drivetrain upgrade",
        )
        
        job_dict = job.to_dict()
        assert "recipe" in job_dict
        assert job_dict["recipe"]["ingredients"] == recipe.ingredients
        assert job_dict["recipe"]["steps"] == recipe.steps
    
    def test_job_from_dict_with_recipe(self):
        """Test deserialization with recipe format."""
        original_job = JobIdentification(
            recipe=RecipeInstructions(
                ingredients=[
                    {"name": "cassette [drivetrain_cassettes]", "type": "part"},
                ],
                steps=["Install cassette [drivetrain_cassettes]"],
            ),
            unclear_specifications=[],
            confidence=0.8,
            reasoning="Drivetrain upgrade",
        )
        
        # Serialize and deserialize
        job_dict = original_job.to_dict()
        restored_job = JobIdentification.from_dict(job_dict)
        
        assert restored_job.recipe.steps == original_job.recipe.steps
        assert restored_job.recipe.ingredients == original_job.recipe.ingredients
        assert restored_job.confidence == original_job.confidence
    
    def test_job_backwards_compatibility_with_instructions(self):
        """Test that JobIdentification still works with instructions list."""
        instructions = [
            "Step 1: Remove old chain [drivetrain_chains]",
            "Step 2: Install new cassette [drivetrain_cassettes]",
        ]
        
        job = JobIdentification(
            instructions=instructions,
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Chain replacement",
        )
        
        # Should have converted to recipe format internally
        assert len(job.recipe.steps) == 2
        assert len(job.recipe.ingredients) > 0
        assert "drivetrain_chains" in job.referenced_categories
        assert "drivetrain_cassettes" in job.referenced_categories
    
    def test_recipe_takes_precedence_over_instructions(self):
        """Test that recipe takes precedence when both are provided."""
        recipe = RecipeInstructions(
            ingredients=[
                {"name": "part A [category_a]", "type": "part"},
            ],
            steps=["Use part A [category_a]"],
        )
        
        job = JobIdentification(
            recipe=recipe,
            instructions=["Old instructions that should be ignored"],
            unclear_specifications=[],
            confidence=0.8,
            reasoning="Test",
        )
        
        # Recipe should be used, instructions ignored
        assert len(job.recipe.steps) == 1
        assert job.recipe.steps[0] == "Use part A [category_a]"
        assert job.referenced_categories == ["category_a"]
