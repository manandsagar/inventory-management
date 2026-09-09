<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.stats.eligibleItems') }}</div>
          <div class="stat-value">{{ eligibleItems.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.stats.totalFundedCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalFundedCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.stats.itemsFunded') }}</div>
          <div class="stat-value">{{ fundedItems.length }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-control">
          <input
            type="range"
            class="budget-slider"
            :min="sliderMin"
            :max="sliderMax"
            :step="sliderStep"
            v-model.number="budget"
            @input="clearSubmitSuccess"
          />
          <div class="budget-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Recommended Items</h3>
        </div>
        <div v-if="eligibleItems.length === 0" class="empty-state">
          {{ t('restocking.empty') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.name') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th>{{ t('restocking.table.idealQty') }}</th>
                <th>{{ t('restocking.table.fundedQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.fundedCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in fundedItems" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ item.name }}</td>
                <td>{{ item.category }}</td>
                <td>{{ item.warehouse }}</td>
                <td>{{ idealQtyBySku[item.sku] }}</td>
                <td>{{ item.funded_qty }}</td>
                <td>{{ currencySymbol }}{{ item.unit_cost }}</td>
                <td><strong>{{ currencySymbol }}{{ item.funded_cost.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="place-order-row">
          <button
            class="place-order-btn"
            :disabled="submitting || fundedItems.length === 0"
            @click="submitOrder"
          >
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
          <span v-if="submitSuccess" class="submit-success">{{ t('restocking.orderSuccess') }}</span>
          <span v-if="submitError" class="submit-error">{{ t('restocking.orderError') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const inventoryItems = ref([])
    const demandForecasts = ref([])

    const budget = ref(0)
    const submitting = ref(false)
    const submitSuccess = ref(false)
    const submitError = ref(false)
    let successTimeout = null

    const eligibleItems = computed(() => {
      const inventoryBySku = new Map(inventoryItems.value.map(item => [item.sku, item]))
      const results = []

      for (const forecast of demandForecasts.value) {
        if (forecast.forecasted_demand <= forecast.current_demand) continue

        const item = inventoryBySku.get(forecast.item_sku)
        if (!item) continue

        const ideal_qty = Math.max(0, 2 * item.reorder_point - item.quantity_on_hand)
        if (ideal_qty <= 0) continue

        results.push({
          sku: item.sku,
          name: item.name,
          category: item.category,
          warehouse: item.warehouse,
          unit_cost: item.unit_cost,
          ideal_qty,
          ideal_cost: ideal_qty * item.unit_cost
        })
      }

      return results
    })

    const idealQtyBySku = computed(() => {
      const map = {}
      for (const item of eligibleItems.value) {
        map[item.sku] = item.ideal_qty
      }
      return map
    })

    const totalIdealCost = computed(() => {
      return eligibleItems.value.reduce((sum, item) => sum + item.ideal_cost, 0)
    })

    const sliderMax = computed(() => {
      return Math.max(1, Math.ceil(totalIdealCost.value / 100) * 100)
    })

    const sliderMin = 0

    const sliderStep = computed(() => {
      return Math.max(1, Math.round(sliderMax.value / 100))
    })

    const fundedItems = computed(() => {
      if (totalIdealCost.value === 0) return []

      const fullyFund = budget.value >= totalIdealCost.value
      const ratio = fullyFund ? 1 : budget.value / totalIdealCost.value

      return eligibleItems.value
        .map(item => {
          const funded_qty = fullyFund ? item.ideal_qty : Math.floor(item.ideal_qty * ratio)
          return {
            sku: item.sku,
            name: item.name,
            category: item.category,
            warehouse: item.warehouse,
            unit_cost: item.unit_cost,
            funded_qty,
            funded_cost: funded_qty * item.unit_cost
          }
        })
        .filter(item => item.funded_qty > 0)
    })

    const totalFundedCost = computed(() => {
      return fundedItems.value.reduce((sum, item) => sum + item.funded_cost, 0)
    })

    const clearSubmitSuccess = () => {
      submitSuccess.value = false
      submitError.value = false
    }

    const loadData = async () => {
      try {
        loading.value = true
        const [inventoryData, forecastsData] = await Promise.all([
          api.getInventory(),
          api.getDemandForecasts()
        ])
        inventoryItems.value = inventoryData
        demandForecasts.value = forecastsData
        budget.value = Math.ceil(totalIdealCost.value)
      } catch (err) {
        error.value = 'Failed to load restocking data: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const submitOrder = async () => {
      submitting.value = true
      submitSuccess.value = false
      submitError.value = false
      try {
        const payload = {
          items: fundedItems.value.map(i => ({
            sku: i.sku,
            name: i.name,
            quantity: i.funded_qty,
            unit_cost: i.unit_cost
          })),
          total_budget: budget.value
        }
        await api.createRestockOrder(payload)
        submitSuccess.value = true
        if (successTimeout) clearTimeout(successTimeout)
        successTimeout = setTimeout(() => {
          submitSuccess.value = false
        }, 4000)
      } catch (err) {
        submitError.value = true
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadData)

    return {
      t,
      currencySymbol,
      loading,
      error,
      eligibleItems,
      idealQtyBySku,
      totalIdealCost,
      budget,
      sliderMin,
      sliderMax,
      sliderStep,
      fundedItems,
      totalFundedCost,
      submitting,
      submitSuccess,
      submitError,
      clearSubmitSuccess,
      submitOrder
    }
  }
}
</script>

<style scoped>
.budget-control {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.budget-slider {
  flex: 1;
  accent-color: #2563eb;
}

.budget-value {
  min-width: 120px;
  text-align: right;
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.empty-state {
  color: #64748b;
  padding: 1.5rem 0;
  text-align: center;
}

.place-order-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1.25rem;
}

.place-order-btn {
  padding: 0.625rem 1.5rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.938rem;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.submit-success {
  color: #059669;
  font-weight: 600;
  font-size: 0.875rem;
}

.submit-error {
  color: #dc2626;
  font-weight: 600;
  font-size: 0.875rem;
}
</style>
