<template>
  <div class="recipes-view">

    <!-- Tab bar: Find / Browse / Saved + Scan action button -->
    <div class="tab-bar-row flex gap-xs mb-md" style="align-items:center;">
      <div role="tablist" aria-label="Recipe sections" class="flex gap-xs" style="flex:1;flex-wrap:wrap;">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :id="`tab-${tab.id}`"
          role="tab"
          :aria-selected="activeTab === tab.id"
          :tabindex="activeTab === tab.id ? 0 : -1"
          :class="['btn', 'tab-btn', activeTab === tab.id ? 'btn-primary' : 'btn-secondary']"
          @click="activateTab(tab.id)"
          @keydown="onTabKeydown"
        >{{ tab.label }}</button>
      </div>
      <!-- Scan recipe button — opens modal to photograph a recipe card -->
      <button
        class="btn btn-secondary scan-btn"
        @click="scanModalOpen = true"
        title="Scan a recipe card or cookbook page"
        aria-label="Scan a recipe"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
        Scan
      </button>
    </div>

    <!-- Scan success toast -->
    <div
      v-if="lastScannedTitle"
      class="undo-toast"
      role="status"
      aria-live="polite"
    >
      Saved "{{ lastScannedTitle }}" to your recipes.
    </div>

    <!-- Scan modal -->
    <RecipeScanModal
      v-if="scanModalOpen"
      @close="scanModalOpen = false"
      @saved="onScanSaved"
    />

    <!-- Browse tab -->
    <RecipeBrowserPanel
      v-if="activeTab === 'browse'"
      role="tabpanel"
      aria-labelledby="tab-browse"
      tabindex="0"
      @open-recipe="openRecipeById"
    />

    <!-- Saved tab -->
    <SavedRecipesPanel
      v-else-if="activeTab === 'saved'"
      role="tabpanel"
      aria-labelledby="tab-saved"
      tabindex="0"
      @open-recipe="openRecipeById"
      @go-to-tab="(tab: string) => activateTab(tab as TabId)"
    />

    <!-- Community tab -->
    <CommunityFeedPanel
      v-else-if="activeTab === 'community'"
      role="tabpanel"
      aria-labelledby="tab-community"
      tabindex="0"
      @plan-forked="onPlanForked"
    />

    <!-- Build Your Own tab -->
    <BuildYourOwnTab
      v-else-if="activeTab === 'build'"
      role="tabpanel"
      aria-labelledby="tab-build"
      tabindex="0"
    />

    <!-- Find tab (existing search UI) -->
    <div v-else ref="findPanelRef" role="tabpanel" aria-labelledby="tab-find" tabindex="0">
    <!-- Controls Panel -->
    <div class="card mb-controls">
      <h2 class="section-title text-xl mb-md">Find Recipes</h2>

      <!-- Level Selector -->
      <div class="form-group">
        <label class="form-label">How far should we stretch?</label>
        <div class="flex flex-wrap gap-sm">
          <button
            v-for="lvl in levels"
            :key="lvl.value"
            :class="['btn', 'btn-secondary', { active: recipesStore.level === lvl.value }]"
            @click="recipesStore.level = lvl.value"
            :aria-pressed="recipesStore.level === lvl.value"
            :title="lvl.description"
          >
            {{ lvl.label }}
          </button>
        </div>
        <p v-if="activeLevel" class="level-description text-sm text-secondary mt-xs">
          {{ activeLevel.description }}
        </p>
        <!-- Orch budget pill — only visible when user has opted in (Settings toggle) -->
        <OrchUsagePill class="mt-xs" />
      </div>

      <!-- Surprise Me confirmation -->
      <div v-if="recipesStore.level === 4" class="status-badge status-info wildcard-warning">
        <span id="wildcard-warning-desc">Wildcard mode lets the AI get creative with whatever you have on hand. Results might surprise you.</span>
        <label class="flex-start gap-sm mt-xs">
          <input type="checkbox" v-model="recipesStore.wildcardConfirmed" aria-describedby="wildcard-warning-desc" />
          <span>I understand, go for it</span>
        </label>
      </div>

      <!-- Hard Day Mode — surfaced as a top-level toggle button -->
      <button
        :class="['btn', 'hard-day-btn', recipesStore.hardDayMode ? 'hard-day-active' : 'btn-secondary']"
        @click="recipesStore.hardDayMode = !recipesStore.hardDayMode"
        :aria-pressed="recipesStore.hardDayMode"
      >
        🌿 Hard Day Mode
        <span class="hard-day-sub">{{ recipesStore.hardDayMode ? 'on — quick &amp; simple only' : 'quick, simple recipes only' }}</span>
      </button>
      <p v-if="recipesStore.hardDayMode && recipesStore.result && recipesStore.result.suggestions.length > 0" class="text-muted text-sm mt-xs">
        Tap "Find recipes" again to apply.
      </p>

      <!-- Time Budget selector (kiwi#52) -->
      <!-- Shows when time_first_layout != 'normal' (auto or time_first) -->
      <div v-if="settingsStore.timeFirstLayout !== 'normal'" class="form-group time-bucket-group">
        <label class="form-label">How much time do you have?</label>
        <div class="flex flex-wrap gap-sm">
          <button
            v-for="bucket in timeBuckets"
            :key="bucket.label"
            :class="['btn', 'btn-sm', 'time-bucket-btn',
              recipesStore.maxTotalMin === bucket.value ? 'time-bucket-active' : 'btn-secondary']"
            @click="recipesStore.maxTotalMin = recipesStore.maxTotalMin === bucket.value ? null : bucket.value"
            :aria-pressed="recipesStore.maxTotalMin === bucket.value"
          >
            {{ bucket.label }}
          </button>
        </div>
        <p class="form-hint">
          Filters by time found in recipe steps.
          <span v-if="!recipesStore.maxTotalMin">No time limit set.</span>
        </p>
      </div>

      <!-- Dietary Preferences (collapsible) -->
      <details class="collapsible form-group" @toggle="(e: Event) => dietaryOpen = (e.target as HTMLDetailsElement).open">
        <summary class="collapsible-summary filter-summary" :aria-expanded="dietaryOpen">
          Dietary preferences
          <span v-if="dietaryActive" class="filter-active-dot" aria-label="filters active"></span>
        </summary>

        <div class="collapsible-body">
          <!-- Dietary Constraints — preset checkboxes + other -->
          <div class="form-group">
            <label class="form-label">I eat</label>
            <div class="preset-grid">
              <button
                v-for="opt in dietaryPresets"
                :key="opt.value"
                :class="['btn', 'btn-sm', 'preset-btn', recipesStore.constraints.includes(opt.value) ? 'preset-active' : '']"
                @click="toggleConstraint(opt.value)"
                :aria-pressed="recipesStore.constraints.includes(opt.value)"
              >{{ opt.label }}</button>
            </div>
            <input
              class="form-input mt-sm"
              v-model="constraintInput"
              placeholder="Other (e.g. low-sodium, raw, whole30)"
              aria-describedby="constraint-hint"
              @keydown="onConstraintKey"
              @blur="commitConstraintInput"
              autocomplete="off"
            />
            <span id="constraint-hint" class="form-hint">Press Enter or comma to add.</span>
          </div>

          <!-- Allergies — Big 9 quick-select + other -->
          <div class="form-group">
            <label class="form-label">Allergies <span class="text-muted text-xs">(hard exclusions)</span></label>
            <div class="preset-grid">
              <button
                v-for="allergen in allergenPresets"
                :key="allergen.value"
                :class="['btn', 'btn-sm', 'allergen-btn', recipesStore.allergies.includes(allergen.value) ? 'allergen-active' : '']"
                @click="toggleAllergy(allergen.value)"
                :aria-pressed="recipesStore.allergies.includes(allergen.value)"
              >{{ allergen.label }}</button>
            </div>
            <!-- Active custom allergy tags -->
            <div v-if="recipesStore.allergies.filter(a => !allergenPresets.map(p=>p.value).includes(a)).length > 0" class="tags-wrap flex flex-wrap gap-xs mt-xs">
              <span
                v-for="tag in recipesStore.allergies.filter(a => !allergenPresets.map(p=>p.value).includes(a))"
                :key="tag"
                class="tag-chip status-badge status-error"
              >
                {{ tag }}
                <button class="chip-remove" @click="removeAllergy(tag)" :aria-label="'Remove allergy: ' + tag">×</button>
              </span>
            </div>
            <input
              class="form-input mt-sm"
              v-model="allergyInput"
              placeholder="Other allergen…"
              aria-describedby="allergy-hint"
              @keydown="onAllergyKey"
              @blur="commitAllergyInput"
              autocomplete="off"
            />
            <span id="allergy-hint" class="form-hint">No recipes containing these ingredients will appear.</span>
          </div>

          <!-- Not Today — temporary per-session ingredient exclusions -->
          <div class="form-group">
            <label class="form-label">Not today <span class="text-muted text-xs">(skip these ingredients this session)</span></label>
            <div v-if="recipesStore.excludeIngredients.length > 0" class="tags-wrap flex flex-wrap gap-xs mb-xs">
              <span
                v-for="tag in recipesStore.excludeIngredients"
                :key="tag"
                class="tag-chip status-badge status-warning"
              >
                {{ tag }}
                <button class="chip-remove" @click="removeExcludeIngredient(tag)" :aria-label="'Stop excluding: ' + tag">×</button>
              </span>
            </div>
            <input
              class="form-input"
              v-model="excludeIngredientInput"
              placeholder="e.g. eggs, chicken, broccoli"
              aria-describedby="exclude-hint"
              @keydown="onExcludeIngredientKey"
              @blur="commitExcludeIngredientInput"
              autocomplete="off"
            />
            <span id="exclude-hint" class="form-hint">Recipes containing these won't appear. Press Enter or comma to add.</span>
          </div>

          <!-- Can Make Now toggle -->
          <div class="form-group">
            <label class="flex-start gap-sm shopping-toggle">
              <input type="checkbox" v-model="recipesStore.pantryMatchOnly" :disabled="recipesStore.shoppingMode" />
              <span class="form-label" style="margin-bottom: 0;">Can make now (no missing ingredients)</span>
            </label>
            <p v-if="recipesStore.pantryMatchOnly && !recipesStore.shoppingMode" class="text-sm text-secondary mt-xs">
              Only recipes where every ingredient is in your pantry — no substitutions, no shopping.
            </p>
          </div>

          <!-- Shopping Mode (temporary home — moves to Shopping tab in #71) -->
          <div class="form-group">
            <label class="flex-start gap-sm shopping-toggle">
              <input type="checkbox" v-model="recipesStore.shoppingMode" />
              <span class="form-label" style="margin-bottom: 0;">Open to buying missing ingredients</span>
            </label>
            <p v-if="recipesStore.shoppingMode" class="text-sm text-secondary mt-xs">
              All recipes shown regardless of missing ingredients. Affiliate links appear for anything you'd need to buy.
            </p>
          </div>

          <!-- Max Missing — hidden in shopping mode or pantry-match-only mode -->
          <div v-if="!recipesStore.shoppingMode && !recipesStore.pantryMatchOnly" class="form-group">
            <label class="form-label" for="max-missing">Max Missing Ingredients <span class="text-muted text-xs">(optional)</span></label>
            <input
              id="max-missing"
              type="number"
              class="form-input"
              min="0"
              max="5"
              placeholder="Leave blank for no limit"
              :value="recipesStore.maxMissing ?? ''"
              @input="onMaxMissingInput"
            />
          </div>
        </div>
      </details>

      <!-- Advanced Filters (collapsible) -->
      <details class="collapsible form-group" @toggle="(e: Event) => advancedOpen = (e.target as HTMLDetailsElement).open">
        <summary class="collapsible-summary filter-summary" :aria-expanded="advancedOpen">
          Nutrition Filters{{ activeNutritionFilterCount > 0 ? ` (${activeNutritionFilterCount} active)` : '' }}
          <span v-if="advancedActive" class="filter-active-dot" aria-label="filters active"></span>
        </summary>

        <div class="collapsible-body">
          <!-- Nutrition Filters -->
          <div class="form-group">
            <label class="form-label">Nutrition limits <span class="text-muted text-xs">(per recipe, optional)</span></label>
            <div class="nutrition-filters-grid mt-xs">
              <div class="form-group">
                <label class="form-label" for="filter-max-cal">Max Calories</label>
                <input id="filter-max-cal" type="number" class="form-input" min="0" placeholder="e.g. 600"
                  :value="recipesStore.nutritionFilters.max_calories ?? ''"
                  @input="onNutritionInput('max_calories', $event)" />
              </div>
              <div class="form-group">
                <label class="form-label" for="filter-max-sugar">Max Sugar (g)</label>
                <input id="filter-max-sugar" type="number" class="form-input" min="0" placeholder="e.g. 10"
                  :value="recipesStore.nutritionFilters.max_sugar_g ?? ''"
                  @input="onNutritionInput('max_sugar_g', $event)" />
              </div>
              <div class="form-group">
                <label class="form-label" for="filter-max-carbs">Max Carbs (g)</label>
                <input id="filter-max-carbs" type="number" class="form-input" min="0" placeholder="e.g. 50"
                  :value="recipesStore.nutritionFilters.max_carbs_g ?? ''"
                  @input="onNutritionInput('max_carbs_g', $event)" />
              </div>
              <div class="form-group">
                <label class="form-label" for="filter-max-sodium">Max Sodium (mg)</label>
                <input id="filter-max-sodium" type="number" class="form-input" min="0" placeholder="e.g. 800"
                  :value="recipesStore.nutritionFilters.max_sodium_mg ?? ''"
                  @input="onNutritionInput('max_sodium_mg', $event)" />
              </div>
            </div>
            <p class="text-xs text-muted mt-xs">
              Recipes without nutrition data always appear.
            </p>
          </div>

          <!-- Cuisine Style (Level 3+ only) -->
          <div v-if="recipesStore.level >= 3" class="form-group">
            <label class="form-label">Cuisine Style</label>
            <div class="flex flex-wrap gap-xs">
              <button
                v-for="style in cuisineStyles"
                :key="style.id"
                :class="['btn', 'btn-secondary', 'btn-sm', { active: recipesStore.styleId === style.id }]"
                @click="recipesStore.styleId = recipesStore.styleId === style.id ? null : style.id"
                :aria-pressed="recipesStore.styleId === style.id"
              >{{ style.label }}</button>
            </div>
          </div>

          <!-- Category Filter (Level 1–2 only) -->
          <div v-if="recipesStore.level <= 2" class="form-group">
            <label class="form-label" for="adv-category">Category <span class="text-muted text-xs">(optional)</span></label>
            <input
              id="adv-category"
              class="form-input"
              v-model="categoryInput"
              placeholder="e.g. Breakfast, Asian, Chicken, &lt; 30 Mins"
              @blur="recipesStore.category = categoryInput.trim() || null"
              @keydown.enter="recipesStore.category = categoryInput.trim() || null"
            />
          </div>
        </div>
      </details>

      <!-- Suggest Button -->
      <div class="suggest-row">
        <button
          class="btn btn-primary btn-lg flex-1"
          :disabled="recipesStore.loading || pantryItems.length === 0 || (recipesStore.level === 4 && !recipesStore.wildcardConfirmed)"
          @click="handleSuggest"
        >
          <span v-if="recipesStore.loading && !isLoadingMore">
            <span class="spinner spinner-sm inline-spinner"></span>
            <span v-if="recipesStore.jobStatus === 'queued'">Queued…</span>
            <span v-else-if="recipesStore.jobStatus === 'running'">Generating…</span>
            <span v-else>Finding recipes…</span>
          </span>
          <span v-else>Suggest Recipes</span>
        </button>
        <button
          v-if="recipesStore.level === 3 || recipesStore.level === 4"
          class="btn btn-secondary btn-sm"
          :disabled="isStreaming || recipesStore.loading || pantryItems.length === 0"
          @click="streamRecipe(recipesStore.level as 3 | 4, recipesStore.wildcardConfirmed)"
          title="Stream recipe generation token-by-token via cf-orch"
        >
          {{ isStreaming ? 'Streaming…' : 'Stream (L' + recipesStore.level + ')' }}
        </button>
        <button
          v-if="recipesStore.dismissedCount > 0"
          class="btn btn-ghost btn-sm"
          @click="recipesStore.clearDismissed()"
          title="Show all dismissed recipes again"
        >Clear dismissed ({{ recipesStore.dismissedCount }})</button>
      </div>

      <!-- Empty pantry nudge -->
      <p v-if="pantryItems.length === 0 && !recipesStore.loading" class="text-sm text-muted text-center mt-xs">
        Add items to your pantry first, then tap Suggest to find recipes.
      </p>
    </div>

    <!-- Error -->
    <div v-if="recipesStore.error" role="alert" class="status-badge status-error mb-md">
      {{ recipesStore.error }}
    </div>

    <!-- Streaming recipe generation panel -->
    <div v-if="isStreaming || streamChunks || streamError" class="stream-panel">
      <div v-if="isStreaming" class="stream-status">
        <span class="stream-dot" aria-hidden="true"></span>
        Generating recipe…
      </div>
      <div v-if="streamError" class="stream-error text-sm">{{ streamError }}</div>
      <pre v-if="streamChunks" class="stream-output">{{ streamChunks }}</pre>
    </div>

    <!-- Screen reader announcement for loading + results -->
    <div aria-live="polite" aria-atomic="true" class="sr-only">
      <span v-if="recipesStore.loading && recipesStore.jobStatus === 'queued'">Recipe request queued, waiting for model…</span>
      <span v-else-if="recipesStore.loading && recipesStore.jobStatus === 'running'">Generating your recipe now…</span>
      <span v-else-if="recipesStore.loading">Finding recipes…</span>
      <span v-else-if="recipesStore.result">
        {{ filteredSuggestions.length }} recipe{{ filteredSuggestions.length !== 1 ? 's' : '' }} found
      </span>
    </div>

    <!-- Results -->
    <div v-if="recipesStore.result" class="results-section fade-in" :aria-busy="recipesStore.loading">
      <!-- Rate limit warning -->
      <div
        v-if="recipesStore.result.rate_limited"
        class="status-badge status-warning rate-limit-banner mb-md"
      >
        Today's free suggestions are used up. Your limit resets tomorrow, or
        <a href="#" class="link-inline" @click.prevent="$emit('upgrade')">upgrade for unlimited access</a>.
      </div>

      <!-- Element gaps -->
      <div v-if="recipesStore.result.element_gaps.length > 0" class="card card-secondary mb-md">
        <p class="text-sm font-semibold">These would expand your options:</p>
        <div class="flex flex-wrap gap-xs mt-xs">
          <span
            v-for="gap in recipesStore.result.element_gaps"
            :key="gap"
            class="status-badge status-info"
          >{{ gap }}</span>
        </div>
      </div>

      <!-- Filter bar -->
      <div v-if="recipesStore.result.suggestions.length > 0" class="filter-bar mb-md">
        <input
          class="form-input filter-search"
          v-model="filterText"
          placeholder="Search recipes or ingredients…"
          aria-label="Filter recipes"
          autocomplete="off"
        />
        <div class="filter-chips">
          <template v-if="availableLevels.length > 1">
            <button
              v-for="lvl in availableLevels"
              :key="lvl"
              :class="['filter-chip', { active: filterLevel === lvl }]"
              :aria-pressed="filterLevel === lvl"
              @click="filterLevel = filterLevel === lvl ? null : lvl"
            >{{ levelLabels[lvl] ?? `Level ${lvl}` }}</button>
          </template>
          <button
            :class="['filter-chip', { active: filterMissing === 0 }]"
            :aria-pressed="filterMissing === 0"
            @click="filterMissing = filterMissing === 0 ? null : 0"
          >Can make now</button>
          <button
            :class="['filter-chip', { active: filterMissing === 2 }]"
            :aria-pressed="filterMissing === 2"
            @click="filterMissing = filterMissing === 2 ? null : 2"
          >≤2 missing</button>
          <!-- Complexity filter chips (#55 / #58) -->
          <button
            v-for="cx in ['easy', 'moderate', 'involved']"
            :key="cx"
            :class="['filter-chip', { active: filterComplexity === cx }]"
            :aria-pressed="filterComplexity === cx"
            @click="filterComplexity = filterComplexity === cx ? null : cx"
          >{{ cx }}</button>
          <button
            v-if="hasActiveFilters"
            class="filter-chip filter-chip-clear"
            aria-label="Clear all recipe filters"
            @click="clearFilters"
          ><span aria-hidden="true">✕</span> Clear</button>
        </div>

        <!-- Zero-decision picks (#53 Surprise Me / #57 Just Pick One) -->
        <div v-if="filteredSuggestions.length > 0" class="flex gap-sm flex-wrap" style="margin-top: var(--spacing-sm)">
          <button class="btn btn-secondary btn-sm" @click="pickSurprise" :disabled="filteredSuggestions.length === 0">
            🎲 Surprise me
          </button>
          <button class="btn btn-secondary btn-sm" @click="pickBest" :disabled="filteredSuggestions.length === 0">
            ⚡ Just pick one
          </button>
        </div>
      </div>

      <!-- Spotlight (Surprise Me / Just Pick One result) -->
      <div v-if="spotlightRecipe" class="card spotlight-card slide-up mb-md">
        <div class="flex-between mb-sm">
          <h3 class="text-lg font-bold">{{ spotlightRecipe.title }}</h3>
          <div class="flex gap-xs" style="align-items:center">
            <span v-if="spotlightRecipe.complexity" :class="['status-badge', `complexity-${spotlightRecipe.complexity}`]">{{ spotlightRecipe.complexity }}</span>
            <span v-if="spotlightRecipe.estimated_time_min" class="status-badge status-neutral">~{{ spotlightRecipe.estimated_time_min }}m</span>
            <button class="btn-icon" @click="spotlightRecipe = null" aria-label="Dismiss">✕</button>
          </div>
        </div>
        <p class="text-sm text-secondary mb-xs">{{ spotlightRecipe.match_count }} ingredients matched from your pantry</p>
        <button class="btn btn-primary btn-sm" @click="selectedRecipe = spotlightRecipe; spotlightRecipe = null">
          Cook this
        </button>
        <button class="btn btn-ghost btn-sm ml-sm" @click="pickSurprise">Try another</button>
      </div>

      <!-- No suggestions -->
      <div
        v-if="filteredSuggestions.length === 0"
        class="card text-center text-muted"
      >
        <template v-if="hasActiveFilters">
          <p>No recipes match your filters.</p>
          <button class="btn btn-ghost btn-sm mt-xs" @click="clearFilters">Clear filters</button>
        </template>
        <p v-else>We didn't find matches at this level. Try <button class="btn btn-ghost btn-sm" @click="recipesStore.level = 1; handleSuggest()">Level 1 — Use What I Have</button> or adjust your filters.</p>
      </div>

      <!-- Recipe Cards -->
      <div class="grid-auto mb-md">
        <div
          v-for="recipe in filteredSuggestions"
          :key="recipe.id"
          class="card slide-up"
        >
          <!-- Header row -->
          <div class="flex-between mb-sm">
            <h3 class="text-lg font-bold recipe-title">{{ recipe.title }}</h3>
            <div class="flex flex-wrap gap-xs" style="align-items:center">
              <span class="status-badge status-success">{{ recipe.match_count }} matched</span>
              <span v-if="recipe.complexity" :class="['status-badge', `complexity-${recipe.complexity}`]">{{ recipe.complexity }}</span>
              <span v-if="recipe.estimated_time_min" class="status-badge status-neutral">~{{ recipe.estimated_time_min }}m</span>
              <span class="status-badge status-info">Level {{ recipe.level }}</span>
              <span v-if="recipe.is_wildcard" class="status-badge status-info">Wildcard</span>
              <span
                v-if="recipe.id"
                :class="['btn-icon', 'btn-bookmark', { active: savedStore.isSaved(recipe.id) }]"
                :aria-label="savedStore.isSaved(recipe.id) ? 'Saved: ' + recipe.title : recipe.title"
                :title="savedStore.isSaved(recipe.id) ? 'Saved' : 'Not saved'"
              >{{ savedStore.isSaved(recipe.id) ? '★' : '☆' }}</span>
              <button
                v-if="recipe.id"
                class="btn-icon btn-dismiss"
                @click="recipesStore.dismiss(recipe.id)"
                :aria-label="'Hide recipe: ' + recipe.title"
              >✕</button>
            </div>
          </div>

          <!-- Notes -->
          <p v-if="recipe.notes" class="text-sm text-secondary mb-sm">{{ recipe.notes }}</p>

          <!-- Matched ingredients (what you already have) -->
          <div v-if="recipe.matched_ingredients?.length > 0" class="ingredient-section mb-sm">
            <p class="text-sm font-semibold ingredient-label ingredient-label-have">From your pantry:</p>
            <div class="flex flex-wrap gap-xs mt-xs">
              <span
                v-for="ing in recipe.matched_ingredients"
                :key="ing"
                class="ingredient-chip ingredient-chip-have"
              >{{ ing }}</span>
            </div>
          </div>

          <!-- Nutrition chips -->
          <div v-if="recipe.nutrition" class="nutrition-chips mb-sm">
            <span v-if="recipe.nutrition.calories != null" class="nutrition-chip">
              <span aria-hidden="true">🔥</span><span class="sr-only">Calories:</span> {{ Math.round(recipe.nutrition.calories) }} kcal
            </span>
            <span v-if="recipe.nutrition.fat_g != null" class="nutrition-chip">
              <span aria-hidden="true">🧈</span><span class="sr-only">Fat:</span> {{ recipe.nutrition.fat_g.toFixed(1) }}g fat
            </span>
            <span v-if="recipe.nutrition.protein_g != null" class="nutrition-chip">
              <span aria-hidden="true">💪</span><span class="sr-only">Protein:</span> {{ recipe.nutrition.protein_g.toFixed(1) }}g protein
            </span>
            <span v-if="recipe.nutrition.carbs_g != null" class="nutrition-chip">
              <span aria-hidden="true">🌾</span><span class="sr-only">Carbs:</span> {{ recipe.nutrition.carbs_g.toFixed(1) }}g carbs
            </span>
            <span v-if="recipe.nutrition.fiber_g != null" class="nutrition-chip">
              <span aria-hidden="true">🌿</span><span class="sr-only">Fiber:</span> {{ recipe.nutrition.fiber_g.toFixed(1) }}g fiber
            </span>
            <span v-if="recipe.nutrition.sugar_g != null" class="nutrition-chip nutrition-chip-sugar">
              <span aria-hidden="true">🍬</span><span class="sr-only">Sugar:</span> {{ recipe.nutrition.sugar_g.toFixed(1) }}g sugar
            </span>
            <span v-if="recipe.nutrition.sodium_mg != null" class="nutrition-chip">
              <span aria-hidden="true">🧂</span><span class="sr-only">Sodium:</span> {{ Math.round(recipe.nutrition.sodium_mg) }}mg sodium
            </span>
            <span v-if="recipe.nutrition.servings != null" class="nutrition-chip nutrition-chip-servings">
              <span aria-hidden="true">🍽️</span><span class="sr-only">Servings:</span> {{ recipe.nutrition.servings }} serving{{ recipe.nutrition.servings !== 1 ? 's' : '' }}
            </span>
            <span v-if="recipe.nutrition.estimated" class="nutrition-chip nutrition-chip-estimated" title="Estimated from ingredient profiles">
              ~ estimated
            </span>
          </div>

          <!-- Missing ingredients -->
          <div v-if="recipe.missing_ingredients.length > 0" class="mb-sm">
            <p class="text-sm font-semibold text-secondary">To complete this recipe:</p>
            <div class="flex flex-wrap gap-xs mt-xs">
              <span
                v-for="ing in recipe.missing_ingredients"
                :key="ing"
                class="status-badge status-info"
              >{{ ing }}</span>
            </div>
          </div>

          <!-- Grocery links for this recipe's missing ingredients -->
          <div v-if="groceryLinksForRecipe(recipe).length > 0" class="mb-sm">
            <p class="text-sm font-semibold">Buy online:</p>
            <div class="flex flex-wrap gap-xs mt-xs">
              <a
                v-for="link in groceryLinksForRecipe(recipe)"
                :key="link.ingredient + link.retailer"
                :href="link.url"
                target="_blank"
                rel="noopener noreferrer"
                class="grocery-link status-badge status-info"
                title="This is an affiliate link"
              >
                {{ link.ingredient }} @ {{ link.retailer }} ↗
              </a>
            </div>
          </div>

          <!-- Prep notes -->
          <div v-if="recipe.prep_notes && recipe.prep_notes.length > 0" class="prep-notes mb-sm">
            <p class="text-sm font-semibold">Before you start:</p>
            <ul class="prep-notes-list mt-xs">
              <li v-for="note in recipe.prep_notes" :key="note" class="text-sm prep-note-item">
                {{ note }}
              </li>
            </ul>
          </div>

          <!-- Directions — always visible; this is the content people came for -->
          <div v-if="recipe.directions.length > 0" class="directions-section">
            <p class="text-sm font-semibold directions-label">Steps</p>
            <ol class="directions-list mt-xs">
              <li v-for="(step, idx) in recipe.directions" :key="idx" class="text-sm direction-step">
                {{ step }}
              </li>
            </ol>
          </div>

          <!-- Swap candidates collapsible — shown after directions per M8 -->
          <details
            v-if="recipe.swap_candidates.length > 0"
            class="collapsible mb-sm"
            @toggle="(e: Event) => toggleSwapOpen(recipe.id, (e.target as HTMLDetailsElement).open)"
          >
            <summary class="text-sm font-semibold collapsible-summary" :aria-expanded="openSwapIds.has(recipe.id)">
              Possible swaps ({{ recipe.swap_candidates.length }})
            </summary>
            <div class="card-secondary mt-xs">
              <div
                v-for="swap in recipe.swap_candidates"
                :key="swap.original_name + swap.substitute_name"
                class="swap-row text-sm"
              >
                <span class="font-semibold">{{ swap.original_name }}</span>
                <span class="text-muted"> → </span>
                <span class="font-semibold">{{ swap.substitute_name }}</span>
                <span v-if="swap.constraint_label" class="status-badge status-info ml-xs">{{ swap.constraint_label }}</span>
                <p v-if="swap.explanation" class="text-muted mt-xs">{{ swap.explanation }}</p>
              </div>
            </div>
          </details>

          <!-- Primary action: open detail panel -->
          <div class="card-actions">
            <button class="btn btn-primary btn-make" @click="openRecipe(recipe)">
              Make this
            </button>
          </div>
        </div>
      </div>

      <!-- Load More -->
      <div v-if="recipesStore.result.suggestions.length > 0" class="load-more-row">
        <button
          class="btn btn-secondary"
          :disabled="recipesStore.loading"
          @click="handleLoadMore"
        >
          <span v-if="recipesStore.loading && isLoadingMore">
            <span class="spinner spinner-sm inline-spinner"></span> Loading…
          </span>
          <span v-else>Load more recipes</span>
        </button>
      </div>

      <!-- Soft Build Your Own nudge when corpus results are sparse -->
      <div
        v-if="!recipesStore.loading && filteredSuggestions.length <= 2 && recipesStore.result"
        class="byo-nudge text-sm text-secondary mt-md"
      >
        Not finding what you want?
        <button class="btn-link" @click="activeTab = 'build'">Try Build Your Own</button>
        to make something from scratch.
      </div>

    </div>

    <!-- Recipe detail panel — mounts as a full-screen overlay -->
    <RecipeDetailPanel
      v-if="selectedRecipe"
      :recipe="selectedRecipe"
      :grocery-links="selectedGroceryLinks"
      @close="selectedRecipe = null"
      @cooked="(recipe) => { onCooked(recipe); selectedRecipe = null }"
    />

    <!-- Empty state when no results yet and pantry has items -->
    <div
      v-if="!recipesStore.result && !recipesStore.loading && pantryItems.length > 0"
      class="card text-center text-muted"
    >
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px;height:40px;color:var(--color-text-muted);margin-bottom:var(--spacing-sm)">
        <path d="M12 8c0 0 4-4 12-4s12 4 12 4v8H12V8z"/>
        <path d="M10 16h28v4l-2 20H12L10 20v-4z"/>
        <line x1="20" y1="24" x2="28" y2="24"/>
      </svg>
      <p class="mt-xs">Tap "Suggest Recipes" to find recipes using your pantry items.</p>
    </div>

    </div><!-- end Find tab -->

    <!-- Recipe load error — announced to screen readers via aria-live -->
    <div v-if="browserRecipeError" role="alert" class="status-badge status-error mb-sm">
      {{ browserRecipeError }}
    </div>

    <!-- Detail panel for browser/saved recipe lookups -->
    <RecipeDetailPanel
      v-if="browserSelectedRecipe"
      :recipe="browserSelectedRecipe"
      :grocery-links="[]"
      @close="browserSelectedRecipe = null"
      @cooked="browserSelectedRecipe = null"
    />

    <!-- Undo toast for "I cooked this" dismiss -->
    <div
      v-if="lastCookedRecipe"
      class="undo-toast"
      role="status"
      aria-live="polite"
    >
      Dismissed from suggestions.
      <button class="btn-link" @click="undoCooked">Undo</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRecipesStore } from '../stores/recipes'
import { useSettingsStore } from '../stores/settings'
import { useInventoryStore } from '../stores/inventory'
import { useSavedRecipesStore } from '../stores/savedRecipes'
import RecipeDetailPanel from './RecipeDetailPanel.vue'
import RecipeBrowserPanel from './RecipeBrowserPanel.vue'
import SavedRecipesPanel from './SavedRecipesPanel.vue'
import CommunityFeedPanel from './CommunityFeedPanel.vue'
import BuildYourOwnTab from './BuildYourOwnTab.vue'
import OrchUsagePill from './OrchUsagePill.vue'
import RecipeScanModal from './RecipeScanModal.vue'
import type { ForkResult } from '../stores/community'
import type { RecipeSuggestion, GroceryLink, StreamTokenResponse } from '../services/api'
import { recipesAPI } from '../services/api'

// ── Scan modal ────────────────────────────────────────────────────────────────
const scanModalOpen = ref(false)
const lastScannedTitle = ref<string | null>(null)

function onScanSaved(recipe: { id: number; title: string }) {
  lastScannedTitle.value = recipe.title
  scanModalOpen.value = false
  // Dismiss the toast after 4 seconds
  setTimeout(() => { lastScannedTitle.value = null }, 4000)
}

// Streaming state
const isStreaming = ref(false)
const streamChunks = ref('')
const streamError = ref<string | null>(null)

const recipesStore = useRecipesStore()
const inventoryStore = useInventoryStore()
const settingsStore = useSettingsStore()

// Tab state
type TabId = 'find' | 'browse' | 'saved' | 'community' | 'build'
const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'saved',     label: 'Saved' },
  { id: 'build',     label: 'Build Your Own' },
  { id: 'community', label: 'Community' },
  { id: 'find',      label: 'Find' },
  { id: 'browse',    label: 'Browse' },
]
const activeTab = ref<TabId>('saved')
const savedStore = useSavedRecipesStore()
// Template ref for the Find-tab panel div (used for focus management on tab switch)
const findPanelRef = ref<HTMLElement | null>(null)

function onTabKeydown(e: KeyboardEvent) {
  const tabIds: TabId[] = ['saved', 'build', 'community', 'find', 'browse']
  const current = tabIds.indexOf(activeTab.value)
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    activateTab(tabIds[(current + 1) % tabIds.length]!)
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    activateTab(tabIds[(current - 1 + tabIds.length) % tabIds.length]!)
  }
}

async function activateTab(tab: TabId) {
  activeTab.value = tab
  await nextTick()
  // Move focus to the newly active panel so keyboard users don't have to Tab
  // through the entire tab bar again to reach the panel content.
  // findPanelRef handles the Find tab (a plain div); other tabs are child
  // components so we locate their panel via querySelector.
  if (tab === 'find' && findPanelRef.value) {
    findPanelRef.value.focus()
  } else {
    const panel = document.querySelector('[role="tabpanel"]') as HTMLElement | null
    panel?.focus()
  }
}

// Community tab: navigate to Find tab after a plan fork (full plan view deferred to Task 9)
function onPlanForked(_payload: ForkResult) {
  activeTab.value = 'find'
}

// Browser/saved tab recipe detail panel (fetches full recipe from API)
const browserSelectedRecipe = ref<RecipeSuggestion | null>(null)

const browserRecipeError = ref<string | null>(null)

async function openRecipeById(recipeId: number) {
  browserRecipeError.value = null
  try {
    browserSelectedRecipe.value = await recipesAPI.getRecipe(recipeId)
  } catch {
    browserRecipeError.value = 'Could not load this recipe. Please try again.'
  }
}

// Collapsible panel open state — kept in sync with DOM toggle event so
// :aria-expanded on <summary> reflects the actual open/closed state
const dietaryOpen = ref(false)
const advancedOpen = ref(false)

// Per-recipe swap section open tracking (Set of recipe IDs whose swap <details> are open)
// Uses reassignment instead of .add()/.delete() so Vue's ref() detects the change
const openSwapIds = ref<Set<number>>(new Set())
function toggleSwapOpen(recipeId: number, isOpen: boolean) {
  const next = new Set(openSwapIds.value)
  isOpen ? next.add(recipeId) : next.delete(recipeId)
  openSwapIds.value = next
}

// Human-readable level labels for filter chips (avoids "Lv1" etc. for screen readers)
const levelLabels: Record<number, string> = {
  1: 'Use What I Have',
  2: 'Allow Swaps',
  3: 'Get Creative',
  4: 'Surprise Me',
}

// Local input state for tags
const constraintInput = ref('')
const allergyInput = ref('')
const excludeIngredientInput = ref('')
const categoryInput = ref('')
const isLoadingMore = ref(false)

// Recipe detail panel (Find tab)
const selectedRecipe = ref<RecipeSuggestion | null>(null)

// Filter state (#21)
const filterText = ref('')
const filterLevel = ref<number | null>(null)
const filterMissing = ref<number | null>(null)
const filterComplexity = ref<string | null>(null)
const spotlightRecipe = ref<RecipeSuggestion | null>(null)

const availableLevels = computed(() => {
  if (!recipesStore.result) return []
  return [...new Set(recipesStore.result.suggestions.map((r) => r.level))].sort()
})

const filteredSuggestions = computed(() => {
  if (!recipesStore.result) return []
  let items = recipesStore.result.suggestions
  const q = filterText.value.trim().toLowerCase()
  if (q) {
    items = items.filter((r) =>
      r.title.toLowerCase().includes(q) ||
      r.matched_ingredients.some((i) => i.toLowerCase().includes(q)) ||
      r.missing_ingredients.some((i) => i.toLowerCase().includes(q))
    )
  }
  if (filterLevel.value !== null) {
    items = items.filter((r) => r.level === filterLevel.value)
  }
  if (filterMissing.value !== null) {
    items = items.filter((r) => r.missing_ingredients.length <= filterMissing.value!)
  }
  if (filterComplexity.value !== null) {
    items = items.filter((r) => r.complexity === filterComplexity.value)
  }
  return items
})

const hasActiveFilters = computed(
  () => filterText.value.trim() !== '' || filterLevel.value !== null || filterMissing.value !== null || filterComplexity.value !== null
)

function clearFilters() {
  filterText.value = ''
  filterLevel.value = null
  filterMissing.value = null
  filterComplexity.value = null
}

function pickSurprise() {
  const pool = filteredSuggestions.value
  if (!pool.length) return
  const exclude = spotlightRecipe.value?.id
  const candidates = pool.length > 1 ? pool.filter((r) => r.id !== exclude) : pool
  spotlightRecipe.value = candidates[Math.floor(Math.random() * candidates.length)] ?? null
}

function pickBest() {
  const pool = filteredSuggestions.value
  if (!pool.length) return
  spotlightRecipe.value = pool[0] ?? null
}

const selectedGroceryLinks = computed<GroceryLink[]>(() => {
  if (!selectedRecipe.value || !recipesStore.result) return []
  const missing = new Set(selectedRecipe.value.missing_ingredients.map((s) => s.toLowerCase()))
  return recipesStore.result.grocery_links.filter((l) => missing.has(l.ingredient.toLowerCase()))
})

function openRecipe(recipe: RecipeSuggestion) {
  selectedRecipe.value = recipe
}

const lastCookedRecipe = ref<{ id: number; title: string } | null>(null)
let undoTimer: ReturnType<typeof setTimeout> | null = null

function onCooked(recipe: RecipeSuggestion) {
  recipesStore.logCook(recipe.id, recipe.title)
  recipesStore.dismiss(recipe.id)
  lastCookedRecipe.value = { id: recipe.id, title: recipe.title }
  if (undoTimer) clearTimeout(undoTimer)
  undoTimer = setTimeout(() => {
    lastCookedRecipe.value = null
  }, 12000)
}

function undoCooked() {
  if (!lastCookedRecipe.value) return
  recipesStore.undismiss(lastCookedRecipe.value.id)
  if (undoTimer) clearTimeout(undoTimer)
  lastCookedRecipe.value = null
}

onUnmounted(() => { if (undoTimer) clearTimeout(undoTimer) })

const levels = [
  { value: 1, label: 'Use What I Have',  description: 'Finds recipes you can make right now using exactly what\'s in your pantry.' },
  { value: 2, label: 'Allow Swaps',      description: 'Same as above, plus recipes where one or two ingredients can be substituted.' },
  { value: 3, label: 'Get Creative',     description: 'AI builds recipes in your chosen cuisine style from what you have. Requires paid tier.' },
  { value: 4, label: 'Surprise Me 🎲',   description: 'Fully AI-generated — open-ended and occasionally unexpected. Requires paid tier.' },
]

const dietaryPresets = [
  { label: 'Vegetarian', value: 'vegetarian' },
  { label: 'Vegan',      value: 'vegan' },
  { label: 'Gluten-free', value: 'gluten-free' },
  { label: 'Dairy-free', value: 'dairy-free' },
  { label: 'Keto',       value: 'keto' },
  { label: 'Low-carb',   value: 'low-carb' },
  { label: 'Halal',      value: 'halal' },
  { label: 'Kosher',     value: 'kosher' },
]

const allergenPresets = [
  { label: 'Peanuts',    value: 'peanuts' },
  { label: 'Tree nuts',  value: 'tree nuts' },
  { label: 'Shellfish',  value: 'shellfish' },
  { label: 'Fish',       value: 'fish' },
  { label: 'Milk',       value: 'milk' },
  { label: 'Eggs',       value: 'eggs' },
  { label: 'Wheat',      value: 'wheat' },
  { label: 'Soy',        value: 'soy' },
  { label: 'Sesame',     value: 'sesame' },
]

function toggleConstraint(value: string) {
  if (recipesStore.constraints.includes(value)) {
    recipesStore.constraints = recipesStore.constraints.filter((c) => c !== value)
  } else {
    recipesStore.constraints = [...recipesStore.constraints, value]
  }
}

function toggleAllergy(value: string) {
  if (recipesStore.allergies.includes(value)) {
    recipesStore.allergies = recipesStore.allergies.filter((a) => a !== value)
  } else {
    recipesStore.allergies = [...recipesStore.allergies, value]
  }
}

const dietaryActive = computed(() =>
  recipesStore.constraints.length > 0 ||
  recipesStore.allergies.length > 0 ||
  recipesStore.excludeIngredients.length > 0 ||
  recipesStore.shoppingMode
)

const advancedActive = computed(() =>
  Object.values(recipesStore.nutritionFilters).some((v) => v !== null) ||
  recipesStore.maxMissing !== null ||
  !!recipesStore.category ||
  !!recipesStore.styleId
)

// #46 — count of active nutrition filters so the summary is informative when collapsed
const activeNutritionFilterCount = computed(() =>
  Object.values(recipesStore.nutritionFilters ?? {}).filter((v) => v !== null).length
)

const activeLevel = computed(() => levels.find(l => l.value === recipesStore.level))

// Time budget buckets for the time-first entry selector (kiwi#52)
const timeBuckets = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '45 min', value: 45 },
  { label: '1 hour', value: 60 },
  { label: '90 min', value: 90 },
]

const cuisineStyles = [
  { id: 'italian',           label: 'Italian' },
  { id: 'mediterranean',     label: 'Mediterranean' },
  { id: 'east_asian',        label: 'East Asian' },
  { id: 'latin',             label: 'Latin' },
  { id: 'eastern_european',  label: 'Eastern European' },
]

// Pantry items sorted expiry-first (available items only)
const pantryItems = computed(() => {
  const sorted = [...inventoryStore.items]
    .filter((item) => item.status === 'available')
    .sort((a, b) => {
      if (!a.expiration_date && !b.expiration_date) return 0
      if (!a.expiration_date) return 1
      if (!b.expiration_date) return -1
      return new Date(a.expiration_date).getTime() - new Date(b.expiration_date).getTime()
    })
  return sorted.map((item) => item.product_name).filter(Boolean) as string[]
})

// Secondary-state items: expired but still usable in specific recipes.
// Maps product_name → secondary_state label (e.g. "Bread" → "stale").
// Sent alongside pantry_items so the recipe engine can boost relevant recipes.
const secondaryPantryItems = computed<Record<string, string>>(() => {
  const result: Record<string, string> = {}
  for (const item of inventoryStore.items) {
    if (item.secondary_state && item.product_name) {
      result[item.product_name] = item.secondary_state
    }
  }
  return result
})

// Grocery links relevant to a specific recipe's missing ingredients
function groceryLinksForRecipe(recipe: RecipeSuggestion): GroceryLink[] {
  if (!recipesStore.result) return []
  return recipesStore.result.grocery_links.filter((link) =>
    recipe.missing_ingredients.includes(link.ingredient)
  )
}

// Tag input helpers — constraints
function addConstraint(value: string) {
  const tag = value.trim().toLowerCase()
  if (tag && !recipesStore.constraints.includes(tag)) {
    recipesStore.constraints = [...recipesStore.constraints, tag]
  }
  constraintInput.value = ''
}

function onConstraintKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addConstraint(constraintInput.value)
  }
}

function commitConstraintInput() {
  if (constraintInput.value.trim()) {
    addConstraint(constraintInput.value)
  }
}

// Tag input helpers — allergies
function addAllergy(value: string) {
  const tag = value.trim().toLowerCase()
  if (tag && !recipesStore.allergies.includes(tag)) {
    recipesStore.allergies = [...recipesStore.allergies, tag]
  }
  allergyInput.value = ''
}

function removeAllergy(tag: string) {
  recipesStore.allergies = recipesStore.allergies.filter((a) => a !== tag)
}

function onAllergyKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addAllergy(allergyInput.value)
  }
}

function commitAllergyInput() {
  if (allergyInput.value.trim()) {
    addAllergy(allergyInput.value)
  }
}

function addExcludeIngredient(value: string) {
  const tag = value.trim().toLowerCase()
  if (tag && !recipesStore.excludeIngredients.includes(tag)) {
    recipesStore.excludeIngredients = [...recipesStore.excludeIngredients, tag]
  }
  excludeIngredientInput.value = ''
}

function removeExcludeIngredient(tag: string) {
  recipesStore.excludeIngredients = recipesStore.excludeIngredients.filter((i) => i !== tag)
}

function onExcludeIngredientKey(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addExcludeIngredient(excludeIngredientInput.value)
  }
}

function commitExcludeIngredientInput() {
  if (excludeIngredientInput.value.trim()) {
    addExcludeIngredient(excludeIngredientInput.value)
  }
}

// Max missing number input
function onMaxMissingInput(e: Event) {
  const target = e.target as HTMLInputElement
  const val = parseInt(target.value)
  recipesStore.maxMissing = isNaN(val) ? null : val
}

// Nutrition filter inputs
type NutritionKey = 'max_calories' | 'max_sugar_g' | 'max_carbs_g' | 'max_sodium_mg'
function onNutritionInput(key: NutritionKey, e: Event) {
  const target = e.target as HTMLInputElement
  const val = parseFloat(target.value)
  recipesStore.nutritionFilters[key] = isNaN(val) ? null : val
}

// Streaming recipe generation
async function streamRecipe(level: 3 | 4, wildcardConfirmed = false) {
  isStreaming.value = true
  streamChunks.value = ''
  streamError.value = null

  let tokenData: StreamTokenResponse
  try {
    tokenData = await recipesAPI.getRecipeStreamToken({ level, wildcard_confirmed: wildcardConfirmed })
  } catch (err: unknown) {
    isStreaming.value = false
    streamError.value = err instanceof Error ? err.message : 'Failed to start stream'
    return
  }

  const url = `${tokenData.stream_url}?token=${encodeURIComponent(tokenData.token)}`
  const es = new EventSource(url)

  es.onmessage = (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data)
      if (data.done) {
        es.close()
        isStreaming.value = false
      } else if (data.error) {
        es.close()
        isStreaming.value = false
        streamError.value = data.error
      } else if (data.chunk) {
        streamChunks.value += data.chunk
      }
    } catch {
      // ignore malformed events
    }
  }

  es.onerror = () => {
    es.close()
    isStreaming.value = false
    streamError.value = 'Stream connection lost'
  }
}

// Suggest handler
async function handleSuggest() {
  isLoadingMore.value = false
  await recipesStore.suggest(pantryItems.value, secondaryPantryItems.value)
}

async function handleLoadMore() {
  isLoadingMore.value = true
  await recipesStore.loadMore(pantryItems.value, secondaryPantryItems.value)
  isLoadingMore.value = false
}

onMounted(async () => {
  if (inventoryStore.items.length === 0) {
    await inventoryStore.fetchItems()
  }
  // Pre-load saved recipes so we know immediately whether to redirect
  await savedStore.load()
})

// If Saved tab is empty after loading, bounce to Build Your Own.
// No immediate: true — the immediate fire happens before onMounted runs load(),
// so loading=false and count=0 is the initial unloaded state, not "empty after load".
watch(
  () => ({ loading: savedStore.loading, count: savedStore.saved.length }),
  ({ loading, count }) => {
    if (!loading && count === 0 && activeTab.value === 'saved') {
      activeTab.value = 'build'
    }
  },
)
</script>

<style scoped>
.byo-nudge {
  padding: var(--spacing-sm) 0;
}

.btn-link {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  font-size: inherit;
}

.tab-bar {
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--spacing-sm);
}

.tab-btn {
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  border-bottom: none;
}

.mb-controls {
  margin-bottom: var(--spacing-md);
}

.mb-md {
  margin-bottom: var(--spacing-md);
}

.mb-sm {
  margin-bottom: var(--spacing-sm);
}

.mt-xs {
  margin-top: var(--spacing-xs);
}

.ml-xs {
  margin-left: var(--spacing-xs);
}

.level-description {
  font-style: italic;
  line-height: 1.4;
}

.wildcard-warning {
  display: block;
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
}

.hard-day-toggle {
  cursor: pointer;
  user-select: none;
}

.shopping-toggle {
  cursor: pointer;
  user-select: none;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.chip-remove {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
  line-height: 1;
  color: inherit;
  opacity: 0.7;
  transition: opacity 0.15s;
  min-width: 24px;
  min-height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chip-remove:hover {
  opacity: 1;
  transform: none;
}

.inline-spinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: var(--spacing-xs);
}

.rate-limit-banner {
  display: block;
  padding: var(--spacing-sm) var(--spacing-md);
}

.recipe-title {
  flex: 1;
  margin-right: var(--spacing-sm);
}

.btn-dismiss {
  background: transparent;
  border: none;
  cursor: pointer;
  /* WCAG 2.2 2.5.8: minimum 24×24px touch target */
  min-width: 24px;
  min-height: 24px;
  padding: 4px 6px;
  font-size: 12px;
  line-height: 1;
  color: var(--color-text-muted);
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}

.btn-dismiss:hover {
  color: var(--color-error, #dc2626);
  background: var(--color-error-bg, #fee2e2);
  transform: none;
}

.btn-bookmark {
  background: transparent;
  border: none;
  cursor: pointer;
  /* WCAG 2.2 2.5.8: minimum 24×24px touch target */
  min-width: 24px;
  min-height: 24px;
  padding: 4px 6px;
  font-size: 14px;
  line-height: 1;
  color: var(--color-text-muted);
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
  flex-shrink: 0;
}

.btn-bookmark:hover,
.btn-bookmark.active {
  color: var(--color-warning, #ca8a04);
  background: var(--color-warning-bg, #fef9c3);
  transform: none;
}

/* Saved recipes section */
.saved-header {
  user-select: none;
}

.saved-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.saved-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
}

.saved-row:last-child {
  border-bottom: none;
}

.saved-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-primary);
}

.saved-title:hover {
  text-decoration: underline;
}

/* Filter bar */
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.filter-search {
  width: 100%;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.filter-chip {
  background: var(--color-bg-secondary, #f5f5f5);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 2px 10px;
  font-size: var(--font-size-xs);
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

.filter-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-bg-secondary);
  transform: none;
}

.filter-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.filter-chip-clear {
  border-color: var(--color-error, #dc2626);
  color: var(--color-error, #dc2626);
}

.filter-chip-clear:hover {
  background: var(--color-error-bg, #fee2e2);
  border-color: var(--color-error, #dc2626);
  color: var(--color-error, #dc2626);
}

.suggest-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.btn-ghost {
  background: transparent;
  border: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
  white-space: nowrap;
}

.btn-ghost:hover {
  color: var(--color-primary);
  background: transparent;
  transform: none;
}

.btn-sm {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-size-sm);
}

.load-more-row {
  display: flex;
  justify-content: center;
  margin-bottom: var(--spacing-md);
}

.collapsible {
  border-top: 1px solid var(--color-border);
  padding-top: var(--spacing-sm);
}

.collapsible-summary {
  cursor: pointer;
  list-style: none;
  padding: var(--spacing-xs) 0;
  color: var(--color-primary);
}

.collapsible-summary::-webkit-details-marker {
  display: none;
}

.collapsible-summary::before {
  content: '▶ ';
  font-size: 10px;
}

details[open] .collapsible-summary::before {
  content: '▼ ';
}

.filter-summary {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-weight: 500;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.filter-active-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}

.collapsible-body {
  padding-top: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* Hard Day Mode button */
.hard-day-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  justify-content: flex-start;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
}

.hard-day-active {
  background: var(--color-success, #2d7a4f);
  color: white;
  border-color: var(--color-success, #2d7a4f);
}

.hard-day-sub {
  font-size: var(--font-size-xs, 0.75rem);
  font-weight: 400;
  opacity: 0.85;
  margin-left: auto;
}

/* Time bucket selector (kiwi#52) */
.time-bucket-group {
  margin-top: var(--spacing-sm, 0.5rem);
}

.time-bucket-btn {
  min-width: 4.5rem;
  border-radius: var(--radius-full, 9999px);
  font-weight: 500;
}

.time-bucket-active {
  background: var(--color-primary, #1a6b4a);
  color: white;
  border-color: var(--color-primary, #1a6b4a);
}

/* Preset grid — auto-fill 2+ columns */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: var(--spacing-xs);
}

.preset-btn {
  justify-content: center;
  text-align: center;
}

.preset-active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.allergen-btn {
  justify-content: center;
  text-align: center;
}

.allergen-active {
  background: var(--color-error, #c0392b);
  color: white;
  border-color: var(--color-error, #c0392b);
}

.swap-row {
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-border);
}

.swap-row:last-child {
  border-bottom: none;
}

.prep-notes-list {
  padding-left: var(--spacing-lg);
  list-style-type: disc;
}

.prep-note-item {
  margin-bottom: var(--spacing-xs);
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.ingredient-section {
  border-top: 1px solid var(--color-border);
  padding-top: var(--spacing-sm);
}

.ingredient-label {
  margin-bottom: 0;
}

.ingredient-label-have {
  color: var(--color-success, #16a34a);
}

.ingredient-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.ingredient-chip-have {
  background: var(--color-success-bg, #dcfce7);
  color: var(--color-success, #16a34a);
}

.directions-section {
  border-top: 1px solid var(--color-border);
  padding-top: var(--spacing-sm);
  margin-top: var(--spacing-xs);
}

.directions-label {
  color: var(--color-text-secondary);
  text-transform: uppercase;
  font-size: var(--font-size-xs);
  letter-spacing: 0.05em;
  margin-bottom: var(--spacing-xs);
}

.directions-list {
  padding-left: var(--spacing-lg);
}

.direction-step {
  margin-bottom: var(--spacing-sm);
  line-height: 1.6;
}

.grocery-link {
  text-decoration: none;
  cursor: pointer;
  transition: opacity 0.2s;
}

.grocery-link:hover {
  opacity: 0.8;
}

.card-actions {
  border-top: 1px solid var(--color-border);
  padding-top: var(--spacing-sm);
  margin-top: var(--spacing-sm);
  display: flex;
  justify-content: flex-end;
}

.btn-make {
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs) var(--spacing-md);
}

.spotlight-card {
  border: 2px solid var(--color-primary);
  background: linear-gradient(135deg, var(--color-bg-elevated) 0%, rgba(232, 168, 32, 0.06) 100%);
}

.results-section {
  margin-top: var(--spacing-md);
}

.nutrition-summary {
  cursor: pointer;
}

.nutrition-filters-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-sm);
}

.nutrition-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.nutrition-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: var(--font-size-xs);
  background: var(--color-bg-secondary, #f5f5f5);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.nutrition-chip-sugar {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.nutrition-chip-servings {
  background: var(--color-info-bg);
  color: var(--color-info-light);
}

.nutrition-chip-estimated {
  font-style: italic;
  opacity: 0.7;
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .flex-between {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-xs);
  }

  .recipe-title {
    margin-right: 0;
  }

  .nutrition-filters-grid {
    grid-template-columns: 1fr;
  }
}

.undo-toast {
  position: fixed;
  bottom: var(--spacing-lg);
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-sm) var(--spacing-md);
  box-shadow: var(--shadow-md);
  font-size: var(--font-size-sm);
  z-index: 100;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.undo-toast .btn-link {
  min-height: 24px;
  padding: 2px 4px;
}

.stream-panel {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.stream-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.stream-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
  animation: stream-pulse 1.2s ease-in-out infinite;
}

@keyframes stream-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.stream-error {
  color: var(--color-danger, #e05c5c);
  margin-bottom: 0.5rem;
}

.stream-output {
  font-family: inherit;
  white-space: pre-wrap;
  font-size: var(--font-size-sm);
  color: var(--color-text);
  margin: 0;
  max-height: 400px;
  overflow-y: auto;
}
</style>
