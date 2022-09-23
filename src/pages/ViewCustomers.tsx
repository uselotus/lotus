import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/Customers/CustomerTable";
import { CustomerSummary, CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);
  const queryClient = useQueryClient();

  const { data, isLoading }: UseQueryResult<CustomerSummary> =
    useQuery<CustomerSummary>(["customer_list"], () =>
      Customer.getCustomers().then((res) => {
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
          <CustomerTable customerArray={data.customers} />
        )}
      </div>
    </div>
  );
};

export default ViewCustomers;
