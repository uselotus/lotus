import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import { CustomerSummary, CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult } from "react-query";

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  const { data, isLoading }: UseQueryResult<CustomerSummary> =
    useQuery<CustomerSummary>(["customer_list"], () =>
      Customer.getCustomers().then((res) => {
        return res;
      })
    );
  useEffect(() => {
    Customer.getCustomers().then((data) => {
      setCustomers(data.customers);
    });
  }, []);

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
