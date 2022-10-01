import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/Customers/CustomerTable";
import {
  CustomerPlus,
  CustomerTableItem,
  CustomerTotal,
} from "../types/customer-type";
import { Customer } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);
  const queryClient = useQueryClient();

  const { data, isLoading }: UseQueryResult<CustomerPlus[]> = useQuery<
    CustomerPlus[]
  >(["customer_list"], () =>
    Customer.getCustomers().then((res) => {
      console.log;
      return res;
    })
  );
  const { data: customerTotals, isLoading: totalLoading } = useQuery<
    CustomerTotal[]
  >(["customer_totals"], () =>
    Customer.getCustomerTotals().then((res) => {
      return res;
    })
  );

  return (
    <div>
      <h1 className="text-3xl font-main ">Customers</h1>
      <div>
        {isLoading || data === undefined ? (
          <LoadingSpinner />
        ) : (
          <CustomerTable customerArray={data} totals={customerTotals} />
        )}
      </div>
    </div>
  );
};

export default ViewCustomers;
