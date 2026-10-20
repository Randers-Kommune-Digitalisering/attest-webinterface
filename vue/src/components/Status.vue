<script setup>
import { ref } from 'vue';

import { getExpressStatus } from '@/backendService';

const statusExpress = ref(null);
// Express status
getExpressStatus()
    .then(data => statusExpress.value = data)

</script>

<template>
    Herunder kan du se om hvorvidt du bruger Express server. Vær opmærksom på at Express serveren ikke kører hvis du bruger Vite i udviklingsmiljø.
    <div>
        <span>Express</span>:
        <span v-if="statusExpress" class="green heavy">{{statusExpress}}</span>
        <span v-else class="red heavy">Not running</span>
    </div>
</template>

<style scoped>
    div
    {
        margin-top: 1rem;
        padding-left: 1.5rem;
        border-left: 0.1rem solid var(--color-border);
    }
</style>
