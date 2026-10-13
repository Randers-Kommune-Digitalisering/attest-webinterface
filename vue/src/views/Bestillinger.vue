
<script setup>
    import { ref } from 'vue'

    import Content from '@/components/Content.vue'
    import Attester from '@/components/Attester.vue'
    import attestTyper from '@/assets/attestTypes.json'

    const currentAttestTypes = ref(attestTyper)

    const selectedType = ref(null)
    const selectedSubType = ref(null)
    const selectedTypeArray = ref([null, null])
    //const orderCount = ref(null)

    const emit = defineEmits(['updateOrderCount', 'setOrderCount'])

    const callUpdate = () => { // Updating order count in header
        emit('updateOrderCount')
    }
    const callSetCount = (count) => {
        console.log("Setting order count to " + count)
        emit('setOrderCount', count)
    }
    const updateOrdersCount = () => { // Updating order count for individual types
        fetchOrderCount()
    }

    function setAttestType(typeUid, subTypeUid = -1)
    {
        selectedType.value = typeUid
        selectedSubType.value = subTypeUid
        selectedTypeArray.value = [typeUid, subTypeUid]
    }

    function fetchOrderCount()
    {
        //console.log("Fetching order count")

        fetch('/api/ordercount')
            .then(response => response = response.json())
            //.then(value => orderCount.value = value)
            .then(value => {
                value = Array.isArray(value) ? value : [value]

                attestTyper.forEach(element => {
                    var index = value.findIndex(x => x.attestType === element.typeId && x.attestSubType === element.subTypeId)
                    element.count = index != -1 ? value[index].count : 0
                })

                delete currentAttestTypes.value
                currentAttestTypes.value = JSON.parse(JSON.stringify(attestTyper))
            })
    }

    callUpdate()
    fetchOrderCount()

</script>

<template>

    <h2>Bestillinger</h2>

    <Content>
    <div class="buttonArray">

        <button
            v-if="currentAttestTypes "
            v-for="attestType in currentAttestTypes"
            :class="!(selectedType == attestType.typeId && selectedSubType == attestType.subTypeId) ? attestType.count > 0 ? 'orange' : 'gray' : ''"
            @click="setAttestType(attestType.typeId, attestType.subTypeId)">

            <div class="content">
                <div class="count" v-if="attestType.count > 0">{{attestType.count}}</div>
                <div class="text">
                    {{ attestType.name }}

                    <div class="sub">
                        {{ attestType.description }}
                    </div>
                </div>
            </div>

        </button>
        
    </div>
    </Content>

    <Attester v-if="selectedType != null && selectedSubType != null"
                @updateOrdersCount="updateOrdersCount"
                @updateOrderCount="callUpdate"
                @setOrderCount="callSetCount"
                :attestTypes="selectedTypeArray"></Attester>
    
</template>

<style scoped>
    .buttonArray {
        display:flex;
        flex-wrap:wrap;
        gap: 0.5rem;
    }
    button {
        height: 8rem;
        width: 19rem;
        font-size: 0.9em;

        font-weight: 300;
        text-transform: unset;
        line-height: normal;

        padding: 0rem;
        margin: 0rem;
    }
        button .content
        {
            position:relative;
            height: 100%;
        }
            button .content .count
            {
                position: absolute;
                padding: 0.3rem 0.6rem;
                border-bottom-right-radius: 0.5rem;
                left: 0rem;
                top: 0rem;
                background-color: #00000018;
            }
            button .content .text
            {
                position:relative;
                text-wrap: wrap;
                top: 50%;
                transform: translate(0, -50%);
                padding: 0rem 0.5rem;
            }
            button .content .sub
            {
                max-width: 100%;
                text-wrap: wrap;
                font-size: 0.7em;
                margin-top: 1rem;
                padding: 0rem 0.5rem;
            }
        button.gray
        {
            background-color: var(--color-border-dark);
        }
        button.gray:hover
        {
            background-color: var(--color-border);
        }
</style>