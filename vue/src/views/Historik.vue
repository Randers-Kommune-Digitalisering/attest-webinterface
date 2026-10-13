<script setup>
    import { ref } from 'vue'
    import dayjs from 'dayjs'

    import Content from '@/components/Content.vue'
    import attestTyper from '@/assets/attestTypes.json'
    import IconTable from '@/components/icons/IconTable.vue'

    // Get orders

    const allOrders = ref([])
    const orders = ref([])
    const isSearchingOrders = ref(false)
    const searchKeyword = ref("")

    fetch('/api/history/ordered')
    .then(response => response = response.json())
    //.then(value => value = filterByType(value))
    .then(value => allOrders.value = value)
    .then(value => orders.value = value)


    const allOrdersFinished = ref([])
    const ordersFinished = ref([])
    const isSearchingFinishedOrders = ref(false)
    const searchFinishedKeyword = ref("")

    fetch('/api/history/completed')
    .then(response => response = response.json())
    //.then(value => value = filterByType(value))
    .then(value => allOrdersFinished.value = value)
    .then(value => ordersFinished.value = value.slice(0, 10))

    function returnOrderStatusColor(erAfvist)
    {
        if(erAfvist == 1)
            return "red"
        else 
            return ""
    }

    function toggleSearchOrders()
    {
        isSearchingOrders.value = !isSearchingOrders.value
        if(!isSearchingOrders.value)
            searchOrders("")
    }
    function toggleSearchFinishedOrders()
    {
        isSearchingFinishedOrders.value = !isSearchingFinishedOrders.value
        if(!isSearchingFinishedOrders.value)
            searchFinishedOrders("")
    }
    
    const searchOrders = (keyword) => {
        if(keyword == "")
            orders.value = allOrders.value.slice(0, 10)
        else
            orders.value = searchList(allOrders.value, keyword)
    }
    
    const searchFinishedOrders = (keyword) => {
        if(keyword == "")
            ordersFinished.value = allOrdersFinished.value.slice(0, 10)
        else
            ordersFinished.value = searchList(allOrdersFinished.value, keyword)
    }


    function searchList(list, keyword)
    {
        keyword = keyword.toLowerCase().trim()
        return list.filter(x => x.rekvirentNavn.toLowerCase().includes(keyword) ||
                                x.rekvirentDQ.toLowerCase().includes(keyword) ||
                                x.rekvirentEmail.toLowerCase().includes(keyword) ||
                                x.cpr.includes(keyword) ||
                                x.cpr.replace("-", "").includes(keyword) ||
                                x.navn.toLowerCase().includes(keyword) )
    }


    const currentSortColumn = ref("bestillingModtaget")
    const currentSortDesc = ref(true)

    function sortList(list, col)
    {
        if(col == currentSortColumn.value)
            currentSortDesc.value = !currentSortDesc.value
        else
        {
            currentSortColumn.value = col
            currentSortDesc.value = true
        }

        return list.sort((a, b) =>
        {
            if(a[col] < b[col])
                return currentSortDesc.value ? -1 : 1

            if(a[col] > b[col])
                return currentSortDesc.value ? 1 : -1

            return 0
        })
    }

    const sortOrders = (col) => {
        orders.value = allOrders.value = sortList(allOrders.value, col)

        if(!isSearchingOrders.value || searchKeyword.value == "")
            orders.value = allOrders.value.slice(0, 10)
            
    }
    const sortFinishedOrders = (col) => {
        ordersFinished.value = allOrdersFinished.value = sortList(allOrdersFinished.value, col)

        if(!isSearchingFinishedOrders.value || searchFinishedKeyword.value == "")
            ordersFinished.value = allOrdersFinished.value.slice(0, 10)
    }


</script>

<template>

    <h2>Historik</h2>

    <Content>
        <template #icon>
            <IconTable />
        </template>
        <template #heading>Afventer modtagelse</template>

        <div class="float-right searchButtonDiv">
            <button :class="isSearchingOrders ? 'gray' : ''" @click="toggleSearchOrders()">
                {{ isSearchingOrders ? 'Luk søgning' : 'Søg i historik'}}</button>
        </div>

        <span class="paragraph">Herunder kan du se bestillinger som er bestilt, men afventer modtagelse fra Politiet.</span>

        <div class="paragraph">
            <table>
                <thead>
                    <tr v-if="isSearchingOrders">
                        <th colspan="5">
                            <input type="text" placeholder="Søg efter igangværende bestilling" v-model="searchKeyword" :onchange="searchOrders(searchKeyword)" />
                        </th>
                    </tr>
                    <tr>
                        <th @click="sortOrders('bestillingModtaget')">Dato <div class="text-small">Anmodet</div></th>
                        <th @click="sortOrders('rekvirentNavn')">Rekvirent <div class="text-small">Navn og mail-adresse</div></th>
                        <th @click="sortOrders('cpr')">Rekvisitus <div class="text-small">CPR-nummer</div></th>
                        <th @click="sortOrders('attestType')">Attest <div class="text-small">Type</div></th>
                        <th @click="sortOrders('bestiltHosPoliti')">Dato <div class="text-small">Bestilt</div></th>
                    </tr>
                </thead>
                
                <tr v-if="orders.length > 0" v-for="order in orders">
                    <td>{{ dayjs(order.bestillingModtaget).format("DD-MM-YYYY") }}</td>
                    <td>{{ order.rekvirentNavn }} <div class="text-small">{{ order.rekvirentEmail }}</div></td>
                    <td>{{ order.cpr }}</td>
                    <td>{{ (attestTyper.find(x => x.typeId == order.attestType)).name }}
                        <div class="text-small">{{ (attestTyper.find(x => x.typeId == order.attestType && x.subTypeId == order.attestSubType)).description }}</div>
                    </td>
                    <td>{{ dayjs(order.bestiltHosPoliti).format("DD-MM-YYYY") }}</td>
                </tr>
                <tr v-else>
                    <td colspan="5">Der er ingen bestillinger at vise.</td>
                </tr>
            </table>
        </div>
    </Content>


    <Content>
        <template #icon>
            <IconTable />
        </template>
        <template #heading>Færdigbehandlet</template>

        <div class="float-right searchButtonDiv">
            <button :class="isSearchingFinishedOrders ? 'gray' : ''" @click="toggleSearchFinishedOrders()">
                {{ isSearchingFinishedOrders ? 'Luk søgning' : 'Søg i historik'}}</button>
        </div>

        <span class="paragraph">Herunder kan du se de seneste 10 bestillinger som er færdigbehandlet.</span>

        <div class="paragraph">
            <table>
                <thead>
                    <tr v-if="isSearchingFinishedOrders">
                        <th colspan="5">
                            <input type="text" placeholder="Søg efter færdigbehandlet bestilling" v-model="searchFinishedKeyword" :onchange="searchFinishedOrders(searchFinishedKeyword)" />
                        </th>
                    </tr>
                    <tr>
                        <th @click="sortFinishedOrders('behandlet')">Dato <div class="text-small">Behandlet</div></th>
                        <th @click="sortFinishedOrders('rekvirentNavn')">Rekvirent <div class="text-small">Navn og mail-adresse</div></th>
                        <th @click="sortFinishedOrders('cpr')">Rekvisitus <div class="text-small">CPR-nummer</div></th>
                        <th @click="sortFinishedOrders('attestType')">Attest <div class="text-small">Type</div></th>
                        <th @click="sortFinishedOrders('erAfvist')">Status</th>
                    </tr>
                </thead>
                
                <tr v-if="ordersFinished.length > 0" v-for="order in ordersFinished">
                    <td>{{ dayjs(order.behandlet).format("DD-MM-YYYY") }}</td>
                    <td>{{ order.rekvirentNavn }} <div class="text-small">{{ order.rekvirentEmail }}</div></td>
                    <td>{{ order.cpr }}</td>
                    <td>{{ (attestTyper.find(x => x.typeId == order.attestType)).name }}
                        <div class="text-small">{{ (attestTyper.find(x => x.typeId == order.attestType)).description }}</div>
                    </td>
                    <td><span :class="returnOrderStatusColor(order.erAfvist)">
                            {{
                            order.erAfvist ?
                                "Afvist" :
                                order.erJournaliseret == 1 ?
                                    "Journaliseret" :
                                        order.erAdviseringAfsendt == 1 ?
                                        'Sendt til rekvirent' : 
                                            order.erDublikat  == 1 ? 
                                                'Dublikat' : 'Modtaget'
                            }}
                        </span>
                        <div class="text-small">
                            <span :class="returnOrderStatusColor(order.erAdviseringAfsendt == 1 ? 0 : order.erDublikat ? 0 : 1)">
                                {{ order.erAdviseringAfsendt == 1 ? 'Adviseret' : order.erDublikat  == 1 ? 'Ignoreret' : 'Ikke adviseret' }}
                            </span>
                        </div></td>
                </tr>
                <tr v-else>
                    <td colspan="5">Der er ingen bestillinger at vise.</td>
                </tr>
            </table>
        </div>
    </Content>
    

</template>

<style scoped>
    th {
        user-select: none;
    }
    th:hover {
        cursor: pointer
    }
    td:not(:first-child, :last-child)
    {
        padding-left: 1rem;
        padding-right: 1rem;
    }
    td:first-child
    {
        padding-right: 1rem;
    }
    td:last-child
    {
        padding-left: 1rem;
    }
    td[colspan="5"]
    {
        padding-right: 0rem;
        padding-left: 0rem;
    }
    .buttons
    {
        display: flex;
    }
    .buttons > :not(:last-child)
    {
        margin-right: 1rem;
    }
    
    a:hover
    {
        cursor:pointer;
    }
    .text-small
    {
        font-size: 0.6em;
        text-transform: uppercase;
        color: var(--color-border-dark);
    }
    .displaynone
    {
        display: none;
    }
    button.gray
    {
        background-color: var(--color-border-dark);
    }
    button.gray:hover
    {
        background-color: var(--color-border);
    }
    .searchButtonDiv 
    {
        transform: translateY(-0.8rem);
    }
</style>