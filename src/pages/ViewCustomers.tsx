import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import { CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";

const customer_data = [
  {
    customer_id: "1",
    name: "Leanne Graham",
    plans: 3,
  },
  {
    customer_id: "2",
    name: "Ervin Howell",
    plans: 2,
  },
  { customer_id: "3", name: "Clementine Bauch", plans: 3 },
  { customer_id: "4", name: "Patricia Lebsack", plans: 2 },
];

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  useEffect(() => {
    Customer.getCustomers().then((data) => {
      setCustomers(data);
    });
  }, []);

  return (
    <div>
      <CustomerTable customerArray={customers} />
    </div>
  );
};

export default ViewCustomers;
