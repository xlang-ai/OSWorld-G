import React from 'react';
import { ArrowUpDown, MoreHorizontal } from 'lucide-react';

// MAKE SURE TO KEEP THE GRID!
// MAKE SURE TO KEEP THE GRID!
// MAKE SURE TO KEEP THE GRID!

const GridTable = () => {
  return (
    <div className="border rounded-md">
<table className="table-auto w-full">
  <thead>
    <tr>
      <th className="border px-4 py-2 bg-gray-100">Name</th>
      <th className="border px-4 py-2 bg-gray-100">Age</th>
      <th className="border px-4 py-2 bg-gray-100">City</th>
      <th className="border px-4 py-2 bg-gray-100">Country</th>
      <th className="border px-4 py-2 bg-gray-100">Occupation</th>
      <th className="border px-4 py-2 bg-gray-100">Email</th>
      <th className="border px-4 py-2 bg-gray-100">Phone</th>
      <th className="border px-4 py-2 bg-gray-100">Address</th>
      <th className="border px-4 py-2 bg-gray-100">State</th>
      <th className="border px-4 py-2 bg-gray-100">Zip Code</th>
      <th className="border px-4 py-2 bg-gray-100">Gender</th>
      <th className="border px-4 py-2 bg-gray-100">Nationality</th>
      <th className="border px-4 py-2 bg-gray-100">Birthday</th>
      <th className="border px-4 py-2 bg-gray-100">Hobbies</th>
      <th className="border px-4 py-2 bg-gray-100 text-right">Operation</th>
    </tr>
  </thead>
  <tbody>
    {[
      { name: 'Alice', age: 28, city: 'New York', country: 'USA', occupation: 'Engineer', email: 'alice@example.com', phone: '123-456-7890', address: '123 St, NY', state: 'NY', zip: '10001', gender: 'Female', nationality: 'USA', birthday: '1995-04-23', hobbies: 'Reading' },
      { name: 'Bob', age: 35, city: 'San Francisco', country: 'USA', occupation: 'Designer', email: 'bob@example.com', phone: '987-654-3210', address: '456 Ave, SF', state: 'CA', zip: '94110', gender: 'Male', nationality: 'USA', birthday: '1988-07-15', hobbies: 'Cycling' },
      { name: 'Carol', age: 42, city: 'Seattle', country: 'USA', occupation: 'Teacher', email: 'carol@example.com', phone: '555-123-4567', address: '789 Rd, Seattle', state: 'WA', zip: '98101', gender: 'Female', nationality: 'USA', birthday: '1981-12-11', hobbies: 'Photography' },
      { name: 'Dean', age: 31, city: 'Chicago', country: 'USA', occupation: 'Artist', email: 'dean@example.com', phone: '444-123-9876', address: '101 Blvd, Chicago', state: 'IL', zip: '60601', gender: 'Male', nationality: 'USA', birthday: '1992-05-19', hobbies: 'Painting' },
      { name: 'Eve', age: 25, city: 'Los Angeles', country: 'USA', occupation: 'Scientist', email: 'eve@example.com', phone: '333-222-1111', address: '202 Ln, LA', state: 'CA', zip: '90001', gender: 'Female', nationality: 'USA', birthday: '1998-02-09', hobbies: 'Traveling' },
      { name: 'Frank', age: 37, city: 'Boston', country: 'USA', occupation: 'Doctor', email: 'frank@example.com', phone: '222-111-4444', address: '303 Ave, Boston', state: 'MA', zip: '02110', gender: 'Male', nationality: 'USA', birthday: '1986-10-03', hobbies: 'Reading' },
      { name: 'Grace', age: 40, city: 'Miami', country: 'USA', occupation: 'Chef', email: 'grace@example.com', phone: '666-555-4444', address: '404 St, Miami', state: 'FL', zip: '33101', gender: 'Female', nationality: 'USA', birthday: '1983-08-14', hobbies: 'Cooking' },
      { name: 'Hank', age: 29, city: 'Austin', country: 'USA', occupation: 'Musician', email: 'hank@example.com', phone: '555-444-3333', address: '505 Rd, Austin', state: 'TX', zip: '73301', gender: 'Male', nationality: 'USA', birthday: '1994-03-25', hobbies: 'Music' },
      { name: 'Ivy', age: 32, city: 'Denver', country: 'USA', occupation: 'Nurse', email: 'ivy@example.com', phone: '444-333-2222', address: '606 Blvd, Denver', state: 'CO', zip: '80201', gender: 'Female', nationality: 'USA', birthday: '1991-01-18', hobbies: 'Running' },
      { name: 'Jack', age: 45, city: 'Dallas', country: 'USA', occupation: 'Lawyer', email: 'jack@example.com', phone: '333-222-5555', address: '707 Ln, Dallas', state: 'TX', zip: '75201', gender: 'Male', nationality: 'USA', birthday: '1978-06-29', hobbies: 'Swimming' },
      { name: 'Kim', age: 33, city: 'Houston', country: 'USA', occupation: 'Engineer', email: 'kim@example.com', phone: '222-111-3333', address: '808 Ave, Houston', state: 'TX', zip: '77001', gender: 'Female', nationality: 'USA', birthday: '1990-11-20', hobbies: 'Hiking' },
      { name: 'Liam', age: 28, city: 'Phoenix', country: 'USA', occupation: 'Software Developer', email: 'liam@example.com', phone: '555-444-3333', address: '909 Rd, Phoenix', state: 'AZ', zip: '85001', gender: 'Male', nationality: 'USA', birthday: '1995-07-14', hobbies: 'Gaming' },
      { name: 'Mona', age: 36, city: 'San Diego', country: 'USA', occupation: 'Manager', email: 'mona@example.com', phone: '111-222-3333', address: '1010 St, San Diego', state: 'CA', zip: '92101', gender: 'Female', nationality: 'USA', birthday: '1987-04-30', hobbies: 'Yoga' },
      { name: 'Nate', age: 50, city: 'Las Vegas', country: 'USA', occupation: 'Retired', email: 'nate@example.com', phone: '333-444-5555', address: '2020 Ln, Vegas', state: 'NV', zip: '89101', gender: 'Male', nationality: 'USA', birthday: '1973-09-11', hobbies: 'Golf' }
    ].map((row, index) => (
      <tr key={index}>
        <td className="border px-4 py-2">{row.name}</td>
        <td className="border px-4 py-2">{row.age}</td>
        <td className="border px-4 py-2">{row.city}</td>
        <td className="border px-4 py-2">{row.country}</td>
        <td className="border px-4 py-2">{row.occupation}</td>
        <td className="border px-4 py-2">{row.email}</td>
        <td className="border px-4 py-2">{row.phone}</td>
        <td className="border px-4 py-2">{row.address}</td>
        <td className="border px-4 py-2">{row.state}</td>
        <td className="border px-4 py-2">{row.zip}</td>
        <td className="border px-4 py-2">{row.gender}</td>
        <td className="border px-4 py-2">{row.nationality}</td>
        <td className="border px-4 py-2">{row.birthday}</td>
        <td className="border px-4 py-2">{row.hobbies}</td>
        <td className="border px-4 py-2 text-right">
          <button className="hover:bg-gray-200 p-1 rounded">Edit</button>
        </td>
      </tr>
    ))}
  </tbody>
</table>
   </div>
  );
};

export default GridTable;